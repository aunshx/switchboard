from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.chat_schema import ChatMessage, ChatRequest, ChatResponse, ToolCallLog
from backend.helpers import catalog, selector
from backend.helpers import config
from backend.helpers.config import (
    EXECUTOR_MODEL,
    MAX_EXPOSED_TOOLS,
    MAX_ROUNDS,
    MOCK_NOW_HUMAN,
    reasoning_kwargs,
)
from backend.helpers.dispatch import dispatch, is_read_only

FIND_TOOLS = "find_tools"

FIND_TOOLS_SPEC: dict[str, Any] = {
    "type": "function",
    "name": FIND_TOOLS,
    "description": (
        "Search the full catalog of 191 workspace tools for capabilities that are not in "
        "your current tool list. Call this when the task needs something none of your "
        "available tools can do. The matching tools become callable on your next turn. "
        "This is a search, not an action: it changes nothing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What capability you need, in plain words.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "strict": True,
}

SYSTEM_PROMPT = f"""
You are an assistant operating a mocked workspace through tools.

Current date and time: {MOCK_NOW_HUMAN}. Treat this as now. Never call a tool just to
discover the date. Resolve "today", "tomorrow", "next week" against it.

The signed-in user is Avery Quinn. Their identifier differs per service:
me@example.com in Gmail, Google Calendar and Google Drive; avery@corp.com in Slack
(user U001), Linear (user_me) and GitHub (login avery). Do not assume one address
works everywhere.

Your tool list is a shortlist drawn from a catalog of 191 tools, so it may be missing
something the request needs. If any part of the request cannot be done with the tools
you currently have, call find_tools with a plain description of the capability you
need, then use whatever it returns on your next turn. Never abandon part of a request
without calling find_tools first, and never silently drop a step.

Your exposed tools plus find_tools are the complete set of capabilities that exist.
If, after calling find_tools, no tool performs the operation the user asked for, then
that operation is not possible here. In that case:
- Say plainly which capability is missing. Name the operation the user asked for.
- Do NOT substitute a different tool because its name looks similar or its effect
  seems close. Deleting a permission, emptying the trash, trashing a different file,
  or editing a file to be empty are NOT a substitute for deleting a file.
- Do NOT claim, imply, or summarise that an action succeeded when no tool performed
  it. An action counts as done only if a tool call returned a successful result for
  exactly that action.
Distinguish "the item does not exist" from "no tool can do this". If both are true,
say both.

How to work:
- Do every part of the request. A request to find something and then send, post or
  create something is not complete until the second part has actually happened.
- Resolve identifiers before acting. Channel names, file names, project names and
  people are not ids. List or search first, then use the id you got back.
- If a tool returns an error, read it and correct the arguments. unknown_tool means
  that tool does not exist; do not retry it. tool_error means the resource is missing
  or the operation is not allowed.
- Report only what the tools actually returned. Never invent an id, a message, a file
  or a result. If something the user asked for does not exist, or no available tool
  can do it, say so plainly and explain what you did find.
- If the request is genuinely ambiguous and guessing could produce the wrong write,
  ask one short clarifying question instead of acting.
- If no tool is needed, just answer.
- Keep the final answer short and concrete.
""".strip()

LAST_TURN: dict[str, Any] = {}


def _to_input_items(messages: list[ChatMessage]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for message in messages:
        if message.role == "tool":
            items.append({"role": "user", "content": f"[tool result] {message.content}"})
        else:
            items.append({"role": message.role, "content": message.content})
    return items


def _latest_query(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content


def _function_calls(output: list[Any]) -> list[Any]:
    return [item for item in output if getattr(item, "type", None) == "function_call"]


def _parse_arguments(call: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_select(query: str, context: str | None = None) -> selector.Selection:
    try:
        return selector.select(query, context)
    except Exception:
        return selector.Selection([], [], [], 0, 0, 0, 0, [])


def _merge(exposed: list[str], incoming: list[str]) -> list[str]:
    added = []
    for name in incoming:
        if name not in exposed and len(exposed) < MAX_EXPOSED_TOOLS:
            exposed.append(name)
            added.append(name)
    return added


def _context_digest(tool_calls: list[ToolCallLog]) -> str:
    if not tool_calls:
        return ""
    lines = []
    for entry in tool_calls[-10:]:
        if entry.error:
            lines.append(f"{entry.name} FAILED - {entry.error[:150]}")
        else:
            lines.append(f"{entry.name} succeeded")
    return "Tool calls already made this turn:\n" + "\n".join(lines)


def _fallback_text(tool_calls: list[ToolCallLog]) -> str:
    if not tool_calls:
        return "I was not able to produce an answer for that."
    succeeded = [c.name for c in tool_calls if c.error is None]
    if succeeded:
        return (
            "I ran out of steps before finishing. I completed these calls: "
            + ", ".join(dict.fromkeys(succeeded))
            + ". Please narrow the request and I will continue."
        )
    return (
        "I could not complete that. Every tool call failed; the last error was: "
        + str(tool_calls[-1].error)
    )


def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    tool_calls: list[ToolCallLog] = []
    query = _latest_query(request.messages)

    selection = _safe_select(query)
    exposed: list[str] = []
    _merge(exposed, selection.names)

    selector_calls = 1
    selector_ms = selection.latency_ms
    selector_input = selection.input_tokens
    selector_cached = selection.cached_tokens
    selector_output = selection.output_tokens
    case_repairs = list(selection.case_repairs)
    dropped_unknown = list(selection.dropped_unknown)
    find_tools_calls = 0

    conversation: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_to_input_items(request.messages),
    ]

    client = selector.client()
    extra = reasoning_kwargs(EXECUTOR_MODEL)
    executor_input = 0
    executor_cached = 0
    executor_output = 0
    rounds = 0
    final_text = ""
    exhausted = False
    failure = ""
    need_reselect = False
    reselect_skipped = 0
    parallel_rounds = 0
    read_cache: dict[Any, Any] = {}
    deduped = 0

    while rounds < MAX_ROUNDS:
        rounds += 1
        if rounds > 1 and not (need_reselect or config.RESELECT_EVERY_ROUND):
            reselect_skipped += 1
        elif rounds > 1:
            need_reselect = False
            again = _safe_select(query, _context_digest(tool_calls))
            selector_calls += 1
            selector_ms += again.latency_ms
            selector_input += again.input_tokens
            selector_cached += again.cached_tokens
            selector_output += again.output_tokens
            case_repairs.extend(again.case_repairs)
            dropped_unknown.extend(again.dropped_unknown)
            _merge(exposed, again.names)

        tools = [*catalog.openai_tools(exposed), FIND_TOOLS_SPEC]
        try:
            response = client.responses.create(
                model=EXECUTOR_MODEL,
                input=conversation,
                tools=tools,
                prompt_cache_key="executor-v1",
                **extra,
            )
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            break
        usage = response.usage
        details = getattr(usage, "input_tokens_details", None)
        executor_input += getattr(usage, "input_tokens", 0)
        executor_cached += getattr(details, "cached_tokens", 0) or 0
        executor_output += getattr(usage, "output_tokens", 0)

        calls = _function_calls(response.output)
        if not calls:
            final_text = (response.output_text or "").strip()
            break

        conversation.extend(response.output)

        parallel = (
            config.PARALLEL_READS
            and len(calls) > 1
            and all(is_read_only(c.name) for c in calls)
        )
        if parallel:
            parallel_rounds += 1
            logs: list[list[ToolCallLog]] = [[] for _ in calls]
            with ThreadPoolExecutor(max_workers=len(calls)) as pool:
                outcomes = list(
                    pool.map(
                        lambda pair: dispatch(
                            pair[1].name,
                            _parse_arguments(pair[1]),
                            logs[pair[0]],
                            read_cache,
                        ),
                        enumerate(calls),
                    )
                )
            deduped += sum(1 for o in outcomes if o.cached)
            payloads = [o.feedback() for o in outcomes]
            for entries in logs:
                tool_calls.extend(entries)
            if any(e.error for entries in logs for e in entries):
                need_reselect = True
            for call, payload in zip(calls, payloads):
                conversation.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(payload, default=str),
                    }
                )
            continue

        for call in calls:
            if call.name == FIND_TOOLS:
                find_tools_calls += 1
                asked = str(_parse_arguments(call).get("query") or query)
                found = _safe_select(asked, _context_digest(tool_calls))
                selector_calls += 1
                selector_ms += found.latency_ms
                selector_input += found.input_tokens
                selector_cached += found.cached_tokens
                selector_output += found.output_tokens
                case_repairs.extend(found.case_repairs)
                dropped_unknown.extend(found.dropped_unknown)
                added = _merge(exposed, found.names)
                need_reselect = True
                payload: Any = {
                    "now_available": added,
                    "already_available": [n for n in found.names if n not in added],
                    "note": "These are callable from your next turn onward."
                    if added
                    else "No new tools matched; nothing in the catalog covers that.",
                }
            else:
                outcome = dispatch(
                    call.name, _parse_arguments(call), tool_calls, read_cache
                )
                if outcome.cached:
                    deduped += 1
                if not outcome.ok:
                    need_reselect = True
                payload = outcome.feedback()
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(payload, default=str),
                }
            )
    else:
        exhausted = True
        try:
            response = client.responses.create(
                model=EXECUTOR_MODEL,
                input=conversation,
                tools=tools,
                tool_choice="none",
                prompt_cache_key="executor-v1",
                **extra,
            )
            usage = response.usage
            executor_input += getattr(usage, "input_tokens", 0)
            executor_output += getattr(usage, "output_tokens", 0)
            final_text = (response.output_text or "").strip()
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"

    if not final_text:
        final_text = _fallback_text(tool_calls)
        if failure:
            final_text = f"{final_text} (stopped early: {failure})"

    LAST_TURN.clear()
    LAST_TURN.update(
        {
            "wall_ms": int((time.perf_counter() - started) * 1000),
            "selector_ms": selector_ms,
            "selector_calls": selector_calls,
            "selector_tools": list(exposed),
            "selector_initial_tools": list(selection.names),
            "selector_case_repairs": case_repairs,
            "selector_dropped_unknown": dropped_unknown,
            "selector_input_tokens": selector_input,
            "selector_cached_tokens": selector_cached,
            "selector_output_tokens": selector_output,
            "find_tools_calls": find_tools_calls,
            "reselect_skipped": reselect_skipped,
            "parallel_rounds": parallel_rounds,
            "deduped_calls": deduped,
            "executor_rounds": rounds,
            "executor_input_tokens": executor_input,
            "executor_cached_tokens": executor_cached,
            "executor_output_tokens": executor_output,
            "tool_calls": len(tool_calls),
            "tool_errors": sum(1 for c in tool_calls if c.error),
            "hit_max_rounds": exhausted,
            "failure": failure,
        }
    )

    return ChatResponse(
        messages=[*request.messages, ChatMessage(role="assistant", content=final_text)],
        tool_calls=tool_calls,
    )
