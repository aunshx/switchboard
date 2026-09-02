from __future__ import annotations

import os

SELECTOR_MODEL = "gpt-4.1-mini"
EXECUTOR_MODEL = "gpt-5-mini"
EXECUTOR_REASONING_EFFORT = "low"

_REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def reasoning_kwargs(model: str) -> dict[str, dict[str, str]]:
    if EXECUTOR_REASONING_EFFORT and model.startswith(_REASONING_PREFIXES):
        return {"reasoning": {"effort": EXECUTOR_REASONING_EFFORT}}
    return {}

MAX_ROUNDS = 8
SELECTOR_MIN_TOOLS = 8
SELECTOR_MAX_TOOLS = 12
MAX_EXPOSED_TOOLS = 40
RESELECT_EVERY_ROUND = False
PARALLEL_READS = False

MOCK_NOW_ISO = "2026-04-08T09:00:00-04:00"
MOCK_NOW_HUMAN = "Wednesday 8 April 2026, 09:00 America/New_York"
MOCK_TIMEZONE = "America/New_York"


def api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return key
