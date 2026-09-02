from __future__ import annotations

import hashlib
import json
import re
import os
import statistics
import unittest
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi.testclient import TestClient

import backend.solution as solution
from backend.helpers.dispatch import READ_ONLY
from backend.main import app

Result = dict[str, Any]
Check = Callable[[Result], tuple[bool, str]]

WRITE_MARKERS = ("SEND", "CREATE", "DELETE", "UPDATE", "PATCH", "REMOVE", "ADD", "MOVE",
                 "EDIT", "EMPTY", "CLEAR", "MODIFY", "INSERT", "REPLY", "TRASH", "MERGE",
                 "PUSH", "STAR", "TRIGGER", "WRITE", "MARK", "DUPLICATE", "FORK", "COPY")


def is_write(name: str) -> bool:
    if name in READ_ONLY:
        return False
    return any(marker in name.upper().split("_") for marker in WRITE_MARKERS)


_SMART = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2014": "-",
          "\u2013": "-", "\u00a0": " "}


def answered(result: Result) -> str:
    text = result["payload"]["messages"][-1]["content"]
    for bad, good in _SMART.items():
        text = text.replace(bad, good)
    return text.lower()


def called(result: Result) -> list[str]:
    return [c["name"] for c in result["payload"]["tool_calls"]]


def writes(result: Result) -> list[str]:
    return [n for n in called(result) if is_write(n)]


def asks_question(result: Result) -> bool:
    text = answered(result)
    return "?" in text


def mentions(result: Result, *needles: str) -> bool:
    text = answered(result)
    return any(n.lower() in text for n in needles)


@dataclass
class Case:
    name: str
    query: str
    expect_tools: list[str]
    min_calls: int
    check: Check
    state_must_be_unchanged: bool = False
    tags: list[str] = field(default_factory=list)


def _no_tools(r: Result) -> tuple[bool, str]:
    return (not called(r), f"expected no tool calls, got {called(r)}")


def _exactly(names: list[str]) -> Check:
    def check(r: Result) -> tuple[bool, str]:
        got = called(r)
        return (got == names, f"expected {names}, got {got}")
    return check


def _contains_all(names: list[str]) -> Check:
    def check(r: Result) -> tuple[bool, str]:
        got = called(r)
        missing = [n for n in names if n not in got]
        return (not missing, f"missing {missing} from {got}")
    return check


def _slack_c001_grew(r: Result) -> tuple[bool, str]:
    log = next(c for c in r["state_after"]["slack"]["channel_messages"]
               if c["channel"] == "C001")
    n = len(log["messages"])
    ok = n == 5 and "slack_send_message" in called(r)
    return (ok, f"C001 has {n} messages (want 5), calls={called(r)}")


def _clarifies_no_write(r: Result) -> tuple[bool, str]:
    if writes(r):
        return (False, f"wrote: {writes(r)}")
    if not asks_question(r):
        return (False, "did not ask a clarifying question")
    return (True, "")


DECLINE_PATTERNS = [
    r"\bcan'?t\b", r"\bcannot\b", r"\bcan not\b",
    r"\bunable\b", r"\bnot able\b", r"\bnot possible\b", r"\bisn'?t possible\b",
    r"\bno\s+(?:\w+\s+){0,3}tools?\b",
    r"\bdo(?:n'?t| not)\s+(?:\w+\s+){0,3}have\b",
    r"\bnone of the\b", r"\bnot available\b",
    r"\bthere(?:'?s| is) no\b", r"\bno way to\b",
    r"\bnot something i can\b", r"\boutside\b", r"\bbeyond what\b",
    r"\blacks?\b", r"\bmissing\b",
]
_DECLINE_RE = re.compile("|".join(DECLINE_PATTERNS))


def declines(r: Result) -> bool:
    return bool(_DECLINE_RE.search(answered(r)))


def _names_capability_gap(r: Result) -> tuple[bool, str]:
    if writes(r):
        return (False, f"wrote: {writes(r)}")
    if not declines(r):
        return (False, f"did not name the missing capability: {answered(r)[:160]}")
    if not mentions(r, "delete", "trash", "remove"):
        return (False, "did not reference the requested operation")
    return (True, "")


def _tool_error_logged(r: Result) -> tuple[bool, str]:
    errors = [c["error"] for c in r["payload"]["tool_calls"] if c["error"]]
    if not errors:
        return (False, f"no tool error logged; calls={called(r)}")
    if not mentions(r, "not found", "does not exist", "doesn't exist", "no message",
                    "couldn't find", "could not find", "no such"):
        return (False, f"did not report the failure honestly: {answered(r)[:120]}")
    return (True, "")


def _out_of_scope(r: Result) -> tuple[bool, str]:
    if writes(r):
        return (False, f"wrote: {writes(r)}")
    if not declines(r):
        return (False, f"did not decline clearly: {answered(r)[:160]}")
    return (True, "")


def _perplexity_launch_delay(r: Result) -> tuple[bool, str]:
    if writes(r):
        return (False, f"wrote: {writes(r)}")
    if "perplexity_search" not in called(r):
        return (False, f"perplexity_search not called; got {called(r)}")
    entry = next(c for c in r["payload"]["tool_calls"] if c["name"] == "perplexity_search")
    if "launch delay" not in json.dumps(entry["arguments"]).lower():
        return (False, f"query lacked the literal substring: {entry['arguments']}")
    if not mentions(r, "compliance", "scope creep", "on-call", "on call"):
        return (False, "answer did not reflect the canned launch-delay content")
    return (True, "")


def _parallel_eligible(r: Result) -> tuple[bool, str]:
    got = called(r)
    want = {"slack_list_conversations", "linear_list_teams"}
    if not want.issubset(set(got)):
        return (False, f"expected both reads, got {got}")
    if any(is_write(n) for n in got):
        return (False, f"unexpected write in {got}")
    if not all(n in READ_ONLY for n in got):
        return (False, f"not all calls read-only: {got}")
    return (True, "")


CASES: list[Case] = [
    Case("01_no_tool", "Hello!", [], 0, _no_tools, True, ["no-tool"]),
    Case("02_single_tool", "What conversations do I have in Slack?",
         ["slack_list_conversations"], 1, _exactly(["slack_list_conversations"]),
         True, ["single"]),
    Case("03_sequential_write",
         "Find the most recent email about the launch and post a summary to the "
         "engineering Slack channel.",
         ["GMAIL_FETCH_EMAILS", "slack_list_conversations", "slack_send_message"], 3,
         _slack_c001_grew, False, ["cross-service", "write"]),
    Case("04_unsatisfiable_search",
         "Find the most recent email about the timelines and post a summary to the "
         "timelines Slack channel.",
         ["GMAIL_FETCH_EMAILS"], 1, _clarifies_no_write, True, ["ambiguous"]),
    Case("05_missing_capability", "Delete budget_2025.xlsx from my Drive.",
         ["GOOGLEDRIVE_FIND_FILE"], 1, _names_capability_gap, True, ["capability-gap"]),
    Case("06_two_reads",
         "List my Slack conversations and also list all the Linear teams in the workspace.",
         ["slack_list_conversations", "linear_list_teams"], 2, _parallel_eligible,
         True, ["parallel"]),
    Case("07_ambiguous_param",
         "Schedule a 30-minute meeting with everyone on the project next week.",
         ["GOOGLECALENDAR_CREATE_EVENT"], 0, _clarifies_no_write, True, ["ambiguous"]),
    Case("08_tool_error",
         "Show me the full contents of the Gmail message with id msg_999.",
         ["GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID"], 1, _tool_error_logged, True, ["error"]),
    Case("09_out_of_scope", "Book me a flight to Tokyo for next Tuesday.",
         [], 0, _out_of_scope, True, ["out-of-scope"]),
    Case("10_perplexity",
         "Search the web for what causes a launch delay and summarise the findings.",
         ["perplexity_search"], 1, _perplexity_launch_delay, False, ["search"]),
]


def _state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, default=str).encode()
    ).hexdigest()


def run_case(client: TestClient, case: Case) -> Result:
    client.post("/reset")
    before = client.get("/state").json()
    response = client.post(
        "/chat", json={"messages": [{"role": "user", "content": case.query}]}
    )
    after = client.get("/state").json()
    metrics = dict(solution.LAST_TURN)
    result: Result = {
        "case": case,
        "status": response.status_code,
        "payload": response.json(),
        "metrics": metrics,
        "state_before": before,
        "state_after": after,
        "state_unchanged": _state_hash(before) == _state_hash(after),
    }
    ok, why = case.check(result)
    if ok and case.state_must_be_unchanged and not result["state_unchanged"]:
        ok, why = False, "state changed but should not have"
    result["ok"] = ok
    result["why"] = why
    return result


def summarise(results: list[Result], run_index: int) -> dict[str, Any]:
    passed = [r for r in results if r["ok"]]
    walls = [r["metrics"].get("wall_ms", 0) for r in results]

    recalls, precisions = [], []
    for r in results:
        expected = set(r["case"].expect_tools)
        exposed = set(r["metrics"].get("selector_tools", []))
        if expected:
            recalls.append(len(expected & exposed) / len(expected))
            if exposed:
                precisions.append(len(expected & exposed) / len(exposed))

    actual_calls = sum(len(r["payload"]["tool_calls"]) for r in results)
    min_calls = sum(r["case"].min_calls for r in results)

    stats = {
        "run": run_index,
        "pass": len(passed),
        "total": len(results),
        "recall": statistics.mean(recalls) if recalls else 0.0,
        "precision": statistics.mean(precisions) if precisions else 0.0,
        "calls": actual_calls,
        "min_calls": min_calls,
        "find_tools_cases": sum(
            1 for r in results if r["metrics"].get("find_tools_calls", 0)
        ),
        "case_repairs": sum(
            len(r["metrics"].get("selector_case_repairs", [])) for r in results
        ),
        "dropped_unknown": sum(
            len(r["metrics"].get("selector_dropped_unknown", [])) for r in results
        ),
        "rounds": [r["metrics"].get("executor_rounds", 0) for r in results],
        "p50_ms": statistics.median(walls) if walls else 0,
        "max_ms": max(walls) if walls else 0,
        "sel_in": sum(r["metrics"].get("selector_input_tokens", 0) for r in results),
        "sel_out": sum(r["metrics"].get("selector_output_tokens", 0) for r in results),
        "exe_in": sum(r["metrics"].get("executor_input_tokens", 0) for r in results),
        "exe_out": sum(r["metrics"].get("executor_output_tokens", 0) for r in results),
    }
    return stats


def print_run(results: list[Result], stats: dict[str, Any]) -> None:
    print(f"\n{'=' * 92}\nRUN {stats['run']}\n{'=' * 92}")
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        m = r["metrics"]
        print(f"  {mark}  {r['case'].name:<24} "
              f"{m.get('wall_ms', 0):>6}ms  r={m.get('executor_rounds', 0)} "
              f"calls={len(r['payload']['tool_calls'])}/{r['case'].min_calls} "
              f"find={m.get('find_tools_calls', 0)}")
        print(f"        tools: {called(r)}")
        if not r["ok"]:
            print(f"        WHY  : {r['why']}")
    print(f"\n  pass {stats['pass']}/{stats['total']}   "
          f"recall {stats['recall']:.2f}  precision {stats['precision']:.2f}   "
          f"calls {stats['calls']} vs min {stats['min_calls']}")
    print(f"  find_tools cases {stats['find_tools_cases']}   "
          f"case_repairs {stats['case_repairs']}   "
          f"dropped_unknown {stats['dropped_unknown']}")
    print(f"  rounds {stats['rounds']}   p50 {stats['p50_ms']}ms   max {stats['max_ms']}ms")
    print(f"  tokens  selector in {stats['sel_in']:,} out {stats['sel_out']:,}  |  "
          f"executor in {stats['exe_in']:,} out {stats['exe_out']:,}")


def run_suite(runs: int = 3) -> None:
    client = TestClient(app)
    per_case: dict[str, list[bool]] = {c.name: [] for c in CASES}
    all_stats = []

    for index in range(1, runs + 1):
        results = [run_case(client, case) for case in CASES]
        for r in results:
            per_case[r["case"].name].append(r["ok"])
        stats = summarise(results, index)
        all_stats.append(stats)
        print_run(results, stats)

    print(f"\n{'=' * 92}\nAGGREGATE OVER {runs} RUNS\n{'=' * 92}")
    print(f"  {'case':<26} {'pass rate':<12} outcomes")
    for name, flags in per_case.items():
        rate = f"{sum(flags)}/{len(flags)}"
        marks = " ".join("P" if f else "F" for f in flags)
        print(f"  {name:<26} {rate:<12} {marks}")

    print()
    for key, label in [("pass", "pass"), ("recall", "recall"), ("precision", "precision"),
                       ("calls", "tool calls"), ("p50_ms", "p50 ms"), ("max_ms", "max ms")]:
        values = [s[key] for s in all_stats]
        if isinstance(values[0], float):
            body = ", ".join(f"{v:.2f}" for v in values)
            spread = f"spread {max(values) - min(values):.2f}"
        else:
            body = ", ".join(str(v) for v in values)
            spread = f"spread {max(values) - min(values)}"
        print(f"  {label:<12} {body:<28} {spread}")


class LocalEvalTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("EVAL"), "set EVAL=1 to run the live eval suite")
    def test_eval_suite(self) -> None:
        run_suite(runs=int(os.environ.get("EVAL_RUNS", "3")))


if __name__ == "__main__":
    run_suite(runs=int(os.environ.get("EVAL_RUNS", "3")))
