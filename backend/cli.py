from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = os.environ.get("MCP_BASE_URL", "http://127.0.0.1:8000")
REPL_HELP = """Commands:
  :help        Show this help text.
  :quit        Exit the REPL.
  :reset       Reset mock service state and clear local chat history.
  :clear       Clear only the local chat history.
  :tools       List available tools.
  :tools text  List tools whose name, service, or description matches text.
  :state       Print the full mock service state snapshot.
  :raw         Print the last raw /chat response JSON.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="CLI client for the MCP case study backend.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    repl_parser = subparsers.add_parser("repl", help="Start an interactive chat REPL.")
    add_base_url_argument(repl_parser)
    repl_parser.set_defaults(func=run_repl)

    chat_parser = subparsers.add_parser("chat", help="Send a one-shot prompt to /chat.")
    add_base_url_argument(chat_parser)
    chat_parser.add_argument("prompt", nargs="+", help="Prompt text to send.")
    chat_parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full JSON response after the formatted output.",
    )
    chat_parser.set_defaults(func=run_chat_command)

    tools_parser = subparsers.add_parser("tools", help="List tools from /tools.")
    add_base_url_argument(tools_parser)
    tools_parser.add_argument("--service", help="Filter tools by service.")
    tools_parser.add_argument(
        "--match",
        help="Case-insensitive substring filter for tool name, service, or description.",
    )
    tools_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show each tool description.",
    )
    tools_parser.set_defaults(func=run_tools_command)

    reset_parser = subparsers.add_parser("reset", help="Reset all mock service state.")
    add_base_url_argument(reset_parser)
    reset_parser.set_defaults(func=run_reset_command)

    state_parser = subparsers.add_parser("state", help="Print the /state snapshot.")
    add_base_url_argument(state_parser)
    state_parser.set_defaults(func=run_state_command)

    return parser


def add_base_url_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Backend base URL. Defaults to {DEFAULT_BASE_URL}.",
    )


def request_json(
    base_url: str,
    method: str,
    path: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    request_data = None
    headers = {"accept": "application/json"}
    if payload is not None:
        request_data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"

    request = Request(
        build_url(base_url, path),
        data=request_data,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        if detail:
            raise RuntimeError(
                f"{method} {path} failed with HTTP {exc.code}: {detail}"
            ) from exc
        raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach {base_url}: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {path} returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{method} {path} returned an unexpected JSON payload.")
    return data


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def run_chat_command(args: argparse.Namespace) -> int:
    prompt = " ".join(args.prompt).strip()
    response = request_json(
        args.base_url,
        "POST",
        "/chat",
        payload={"messages": [{"role": "user", "content": prompt}]},
    )
    render_chat_response(response)
    if args.raw:
        print_json(response, title="Raw Response")
    return 0


def run_tools_command(args: argparse.Namespace) -> int:
    tools_response = request_json(args.base_url, "GET", "/tools")
    tools = filter_tools(
        tools_response.get("tools", []),
        service=args.service,
        match=args.match,
    )
    count = len(tools)
    noun = "tool" if count == 1 else "tools"
    print(f"{count} {noun}")
    if not tools:
        return 0

    service_width = max(len(str(tool.get("service", ""))) for tool in tools)
    for tool in tools:
        service = str(tool.get("service", ""))
        name = str(tool.get("name", ""))
        print(f"{service:<{service_width}}  {name}")
        if args.verbose:
            description = str(tool.get("description") or tool.get("docstring") or "")
            if description:
                print(f"  {description}")
    return 0


def run_reset_command(args: argparse.Namespace) -> int:
    response = request_json(args.base_url, "POST", "/reset")
    service_count = response.get("serviceCount", "?")
    tool_count = response.get("toolCount", "?")
    print(f"Reset complete: {service_count} services, {tool_count} tools.")
    return 0


def run_state_command(args: argparse.Namespace) -> int:
    state = request_json(args.base_url, "GET", "/state")
    print_json(state, title="State")
    return 0


def run_repl(args: argparse.Namespace) -> int:
    print(f"Connected to {args.base_url}")
    print("Type :help for commands.")

    messages: list[dict[str, str]] = []
    last_response: Optional[dict[str, Any]] = None

    while True:
        try:
            raw_input_value = input("mcp> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 130

        user_input = raw_input_value.strip()
        if not user_input:
            continue

        if user_input.startswith(":"):
            try:
                should_continue, messages, last_response = handle_repl_command(
                    user_input,
                    args.base_url,
                    messages,
                    last_response,
                )
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                continue
            if should_continue:
                continue
            return 0

        messages.append({"role": "user", "content": user_input})
        try:
            response = request_json(
                args.base_url,
                "POST",
                "/chat",
                payload={"messages": messages},
            )
        except RuntimeError as exc:
            messages.pop()
            print(str(exc), file=sys.stderr)
            continue
        render_chat_response(response)
        messages = coerce_messages(response.get("messages"))
        last_response = response


def handle_repl_command(
    raw_command: str,
    base_url: str,
    messages: list[dict[str, str]],
    last_response: Optional[dict[str, Any]],
) -> tuple[bool, list[dict[str, str]], Optional[dict[str, Any]]]:
    command, _, remainder = raw_command[1:].partition(" ")
    argument = remainder.strip()

    if command in {"q", "quit", "exit"}:
        return False, messages, last_response

    if command == "help":
        print(REPL_HELP)
        return True, messages, last_response

    if command == "clear":
        print("Local chat history cleared.")
        return True, [], last_response

    if command == "reset":
        run_reset_command(argparse.Namespace(base_url=base_url))
        print("Local chat history cleared.")
        return True, [], None

    if command == "tools":
        run_tools_command(
            argparse.Namespace(
                base_url=base_url,
                service=None,
                match=argument or None,
                verbose=False,
            )
        )
        return True, messages, last_response

    if command == "state":
        run_state_command(argparse.Namespace(base_url=base_url))
        return True, messages, last_response

    if command == "raw":
        if last_response is None:
            print("No chat response available yet.")
        else:
            print_json(last_response, title="Raw Response")
        return True, messages, last_response

    print(f"Unknown command: :{command}")
    print("Type :help for commands.")
    return True, messages, last_response


def filter_tools(
    tools: list[dict[str, Any]],
    service: Optional[str] = None,
    match: Optional[str] = None,
) -> list[dict[str, Any]]:
    filtered = tools
    if service:
        service_casefold = service.casefold()
        filtered = [
            tool
            for tool in filtered
            if str(tool.get("service", "")).casefold() == service_casefold
        ]

    if match:
        match_casefold = match.casefold()
        filtered = [
            tool
            for tool in filtered
            if match_casefold in str(tool.get("name", "")).casefold()
            or match_casefold in str(tool.get("service", "")).casefold()
            or match_casefold in str(tool.get("description", "")).casefold()
        ]

    return sorted(
        filtered,
        key=lambda tool: (str(tool.get("service", "")), str(tool.get("name", ""))),
    )


def coerce_messages(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        return []

    messages: list[dict[str, str]] = []
    for message in raw_messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "assistant"))
        content = str(message.get("content", ""))
        messages.append({"role": role, "content": content})
    return messages


def render_chat_response(response: dict[str, Any]) -> None:
    assistant_message = last_assistant_content(response.get("messages"))
    print_section("Assistant")
    print(assistant_message or "(empty)")

    tool_calls = response.get("tool_calls", [])
    print_section("Tool Calls")
    if not tool_calls:
        print("(none)")
        return

    for index, tool_call in enumerate(tool_calls, start=1):
        if not isinstance(tool_call, dict):
            print(f"{index}. <invalid tool call>")
            continue

        name = str(tool_call.get("name", "<unknown>"))
        error = tool_call.get("error")
        status = "error" if error else "ok"
        print(f"{index}. {name} [{status}]")
        arguments = tool_call.get("arguments", {})
        print(f"   args: {compact_json(arguments)}")
        if error:
            print(f"   error: {error}")


def last_assistant_content(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "assistant":
            return str(message.get("content", ""))
    return ""


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def print_json(data: Any, title: Optional[str] = None) -> None:
    if title:
        print_section(title)
    print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True))


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def normalize_argv(argv: Optional[Sequence[str]]) -> list[str]:
    normalized = list(argv) if argv is not None else sys.argv[1:]
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    if not normalized:
        return ["repl"]
    return normalized


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
