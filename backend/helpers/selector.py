from __future__ import annotations

import json
import time
from typing import Any, NamedTuple

from openai import OpenAI

from backend.helpers import catalog, config
from backend.helpers.config import (
    SELECTOR_MAX_TOOLS,
    SELECTOR_MIN_TOOLS,
    SELECTOR_MODEL,
    api_key,
)

_INSTRUCTIONS = f"""
You are a tool router. Above is the complete catalog of every tool available.

Given a user request, return the names of the tools most likely to be needed.

Return between {SELECTOR_MIN_TOOLS} and {SELECTOR_MAX_TOOLS} names. This is a hard
requirement. Returning fewer than {SELECTOR_MIN_TOOLS} is a failure even when the
request looks like it needs only one tool: the executor sees ONLY what you return, so
a short list with one wrong guess leaves it stuck. Rank best-first, then pad to
{SELECTOR_MIN_TOOLS} with the next most plausible tools from the same services.

Rules:
- Copy names EXACTLY as they appear in the catalog, character for character.
  Casing is inconsistent on purpose: GMAIL_FETCH_EMAILS and slack_send_message are
  both correct as written. Never normalise or guess a name.
- Never invent a name that is not in the catalog above. If the capability the request
  asks for does not exist, return the closest read/search tools instead of inventing
  a plausible-sounding write tool. The catalog above is complete and exact.
- Cover the whole chain, not just the first move. A request that reads from one
  service and writes to another needs the read tools, any lookup tools required to
  resolve ids or channel names, and the write tool.
- Prefer list/search/find tools when ids, channel names, file names, or people must
  be resolved before acting.
- Include a plausible alternative or two when the request is ambiguous, so the
  executor can choose after it sees real data.
- If the request needs no tools at all, still return the closest candidates.
""".strip()

SYSTEM_PROMPT = f"TOOL CATALOG (name | service | description)\n{catalog.DIGEST}\n\n{_INSTRUCTIONS}"

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tools": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["tools"],
    "additionalProperties": False,
}

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=api_key())
    return _client


class Selection(NamedTuple):
    names: list[str]
    case_repairs: list[tuple[str, str]]
    dropped_unknown: list[str]
    latency_ms: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    raw: list[str]


def _user_block(query: str, context: str | None) -> str:
    if not context:
        return f"REQUEST\n{query}"
    return f"REQUEST\n{query}\n\nPROGRESS SO FAR\n{context}"


def select(
    query: str,
    context: str | None = None,
    *,
    model: str | None = None,
) -> Selection:
    model = model or config.SELECTOR_MODEL
    started = time.perf_counter()
    response = client().responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_block(query, context)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "tool_selection",
                "schema": _SCHEMA,
                "strict": True,
            }
        },
        prompt_cache_key="selector-digest-v1",
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    try:
        raw = list(json.loads(response.output_text).get("tools", []))
    except (json.JSONDecodeError, AttributeError):
        raw = []

    checked = catalog.validate([str(name) for name in raw])
    usage = response.usage
    details = getattr(usage, "input_tokens_details", None)

    return Selection(
        names=checked.kept,
        case_repairs=checked.case_repairs,
        dropped_unknown=checked.dropped_unknown,
        latency_ms=latency_ms,
        input_tokens=getattr(usage, "input_tokens", 0),
        cached_tokens=getattr(details, "cached_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0),
        raw=raw,
    )


_PROBES: list[tuple[str, list[str]]] = [
    (
        "What conversations do I have in Slack?",
        ["slack_list_conversations"],
    ),
    (
        "Find the most recent email about the timelines and post a summary to the "
        "timelines Slack channel.",
        ["GMAIL_FETCH_EMAILS", "slack_list_conversations", "slack_send_message"],
    ),
    (
        "Schedule a 30-minute meeting with everyone on the project next week.",
        ["GOOGLECALENDAR_CREATE_EVENT", "linear_list_projects"],
    ),
    (
        "Delete budget_2025.xlsx from my Drive.",
        ["GOOGLEDRIVE_FIND_FILE"],
    ),
]


def _probe() -> None:
    print(f"selector model : {SELECTOR_MODEL}")
    print(f"system prompt  : {catalog.estimate_tokens(SYSTEM_PROMPT):,} tokens")
    print()

    for query, expected in _PROBES:
        selection = select(query)
        hits = [name for name in expected if name in selection.names]
        missing = [name for name in expected if name not in selection.names]

        print("-" * 78)
        print(f"QUERY  {query}")
        print(f"  selected ({len(selection.names)} kept of {len(selection.raw)} returned):")
        for name in selection.names:
            mark = " <-- expected" if name in expected else ""
            print(f"      {name}{mark}")
        print(f"  expected hit   : {len(hits)}/{len(expected)}"
              + (f"   MISSING {missing}" if missing else ""))
        print(f"  case_repairs   : {selection.case_repairs or 'none'}")
        print(f"  dropped_unknown: {selection.dropped_unknown or 'none'}")
        print(f"  latency        : {selection.latency_ms} ms")
        print(f"  tokens         : in {selection.input_tokens:,} "
              f"(cached {selection.cached_tokens:,}) / out {selection.output_tokens:,}")


if __name__ == "__main__":
    _probe()
