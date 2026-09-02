from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, NamedTuple

from backend.github_mock import TOOL_REGISTRY as _GITHUB
from backend.gmail_mock import TOOL_REGISTRY as _GMAIL
from backend.googlecalendar_mock import TOOL_REGISTRY as _GOOGLECALENDAR
from backend.googledrive_mock import TOOL_REGISTRY as _GOOGLEDRIVE
from backend.linear_mock import TOOL_REGISTRY as _LINEAR
from backend.perplexity_mock import TOOL_REGISTRY as _PERPLEXITY
from backend.slack_mock import TOOL_REGISTRY as _SLACK
from backend.tooling import ToolSpec

SPECS: dict[str, ToolSpec] = {
    **_GMAIL,
    **_GOOGLECALENDAR,
    **_GOOGLEDRIVE,
    **_SLACK,
    **_LINEAR,
    **_PERPLEXITY,
    **_GITHUB,
}

TOOL_NAMES: tuple[str, ...] = tuple(sorted(SPECS))
_NAMES_SET = frozenset(TOOL_NAMES)

SERVICES: tuple[str, ...] = tuple(sorted({spec.service for spec in SPECS.values()}))

_BY_SERVICE: dict[str, tuple[str, ...]] = {
    service: tuple(
        sorted(name for name, spec in SPECS.items() if spec.service == service)
    )
    for service in SERVICES
}

_DIGEST_LINES: tuple[str, ...] = tuple(
    f"{name} | {SPECS[name].service} | {SPECS[name].description}" for name in TOOL_NAMES
)

DIGEST: str = "\n".join(_DIGEST_LINES)

_CASEFOLD_BUCKETS: dict[str, list[str]] = defaultdict(list)
for _name in TOOL_NAMES:
    _CASEFOLD_BUCKETS[_name.casefold()].append(_name)

AMBIGUOUS_CASEFOLD: frozenset[str] = frozenset(
    key for key, group in _CASEFOLD_BUCKETS.items() if len(group) > 1
)

_CASEFOLD_INDEX: dict[str, str] = {
    key: group[0]
    for key, group in _CASEFOLD_BUCKETS.items()
    if key not in AMBIGUOUS_CASEFOLD
}


class Validation(NamedTuple):
    kept: list[str]
    case_repairs: list[tuple[str, str]]
    dropped_unknown: list[str]


def is_registered(name: str) -> bool:
    return name in _NAMES_SET


def canonical(name: str) -> str | None:
    if name in _NAMES_SET:
        return name
    return _CASEFOLD_INDEX.get(name.casefold())


def validate(names: list[str]) -> Validation:
    kept: list[str] = []
    case_repairs: list[tuple[str, str]] = []
    dropped_unknown: list[str] = []
    for name in names:
        resolved = canonical(name)
        if resolved is None:
            dropped_unknown.append(name)
            continue
        if resolved != name:
            case_repairs.append((name, resolved))
        if resolved not in kept:
            kept.append(resolved)
    return Validation(kept, case_repairs, dropped_unknown)


def spec(name: str) -> ToolSpec:
    return SPECS[name]


def service_of(name: str) -> str:
    return SPECS[name].service


def names_for_service(service: str) -> tuple[str, ...]:
    return _BY_SERVICE.get(service, ())


def digest_lines() -> tuple[str, ...]:
    return _DIGEST_LINES


def openai_tools(names: list[str]) -> list[dict[str, Any]]:
    from backend.main import get_openai_tools

    return get_openai_tools(names)


def estimate_tokens(text: str) -> int:
    try:
        import tiktoken
    except ImportError:
        return (len(text) + 3) // 4
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def _report() -> None:
    try:
        import tiktoken  # noqa: F401

        method = "tiktoken o200k_base (exact)"
    except ImportError:
        method = "chars/4 (estimate; tiktoken not installed)"

    full_schemas = json.dumps(openai_tools(list(TOOL_NAMES)))
    digest_tokens = estimate_tokens(DIGEST)
    schema_tokens = estimate_tokens(full_schemas)

    print(f"tools           : {len(TOOL_NAMES)}")
    print(f"services        : {len(SERVICES)} -> {', '.join(SERVICES)}")
    print(f"casefold keys   : {len(_CASEFOLD_BUCKETS)}")
    print(f"ambiguous       : {len(AMBIGUOUS_CASEFOLD)}"
          + (f" -> {sorted(AMBIGUOUS_CASEFOLD)}" if AMBIGUOUS_CASEFOLD else " (repair is unambiguous)"))
    print(f"token method    : {method}")
    print()
    print(f"digest tokens   : {digest_tokens:>8,}   ({len(DIGEST):,} chars)")
    print(f"schema tokens   : {schema_tokens:>8,}   ({len(full_schemas):,} chars)")
    print(f"ratio           : {schema_tokens / digest_tokens:>8.1f}x")
    print()
    for service in SERVICES:
        count = len(_BY_SERVICE[service])
        print(f"  {service:<16} {count:>3}")
    print()
    print("first 3 digest lines:")
    for line in _DIGEST_LINES[:3]:
        print(f"  {line}")


if __name__ == "__main__":
    _report()
