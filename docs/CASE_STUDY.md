# MCP Case Study: Multi-Tool Chat Harness

You are given a FastAPI server that exposes **191 mock tools** across seven services (Gmail, Google Calendar, Google Drive, Slack, Linear, GitHub, Perplexity). Your job is to build the system that takes a user message and orchestrates these tools to answer it well.

## What's already given
- `backend/` — FastAPI app, all 191 tools registered and callable in-process via `get_tool_spec(name).invoke(**args)`.
- `GET /tools` — full tool catalog with JSON schemas.
- `POST /reset` — resets all mock state to a fixed fixture.
- `GET /state` — read-only snapshot of all mock state for debugging and verifying end-state.
- `POST /chat` — **stub. This is what you implement.**
- `docs/mcp_tool_definitions.txt` — upstream catalog for reference.

### Where your code goes
- `backend/solution.py` — **edit this file.** It defines the `chat` function that `main.py` registers at `POST /chat`. This is the only file you have to touch to complete the case study.
- `backend/helpers/` — put supporting code here. A placeholder `helpers/helpers.py` is included; add more modules in this package as you split things up.
- `backend/chat_schema.py` — Pydantic models for the `/chat` request/response. Only touch this if you genuinely need a new field on the wire.
- `backend/main.py` — FastAPI wiring (app, middleware, `/health`, `/tools`, `/reset`, route registration). You shouldn't need to edit it.

## What you build
A single endpoint, `POST /chat`, that accepts:

```json
{ "messages": [{ "role": "user", "content": "Find emails about the Q3 budget" }] }
```

and returns the assistant's response plus a log of tool calls made along the way:

```json
{
  "messages": [
    { "role": "user", "content": "Find emails about the Q3 budget" },
    { "role": "assistant", "content": "I found 2 emails about Q3 budget..." }
  ],
  "tool_calls": [
    {
      "name": "GMAIL_FETCH_EMAILS",
      "arguments": { "query": "Q3 budget" },
      "result": { "messages": [] },
      "error": null
    }
  ]
}
```

The `tool_calls` log is how we score you — every tool you invoke during the turn must appear there, with the arguments you passed and the result you got back. The endpoint should orchestrate one or more LLM calls and zero or more tool invocations to answer the user. Model and SDK are your choice — `OPENAI_API_KEY` is wired up but you can swap providers.

## What we care about
Two things, in order:

1. **Tool routing.** 191 tools is well past the point where dumping every schema into every model call works. Most provider tool-call APIs will choke or burn serious tokens at this scale, and even when they don't, the model's tool-selection accuracy degrades. How do you decide which tools the model sees on a given turn? Justify your choice in `DESIGN.md`. **While using AI tools to code is allowed during this assignment, we ask that the design write up be your own work and not AI generated.**
2. **Orchestration loop quality.** Multi-step reasoning, error recovery, knowing when to stop, handling ambiguity, parallel vs. sequential calls.

## How you're scored

We run **automated checks** against your `/chat` endpoint. They cover ~30 scenarios — single-service lookups, cross-service joins, multi-step plans, ambiguous prompts where you should ask, and error paths where you should not fabricate success. State is reset between scenarios.

Alongside that we **track but don't grade** two things: wall-clock latency, and tool-call efficiency (how many tools you called vs. the minimum a task needs). They appear on the scorecard for context — they don't fail you.

The harness prints a scorecard like:

```
  ✓ PASS  [s01_slack_list_conversations]    1410 ms  (1/1 calls)
  ✗ FAIL  [s14_perplexity_then_linear_issue]  4220 ms  (2/2 calls) — missing required tool: linear_create_issue
  ...
  Pass rate: 24/30 (80%)
  Latency:   p50 = 2.1s, p95 = 8.4s, total = 89s
  Tool use:  6/30 scenarios over minimum, +11 extra calls total
  State:     9/10 state checks passed
```

A few example scenarios to anchor what kinds of prompts to expect:

> *"What conversations do I have in Slack?"*  — single tool, single service.
>
> *"Find the most recent email about the Q3 budget and post a summary to the leadership Slack channel."*  — cross-service: Gmail then Slack.
>
> *"Schedule a 30-minute meeting with everyone on the project next week."*  — ambiguous; you should ask which project.
>
> *"Delete the file 'budget_2025.xlsx' from my Drive."*  — file does not exist; explain rather than fabricate.

The examples above are representative, but we may run additional scenarios that you have not seen.

## Setup

Ensure you're in the candidate/ directory

```
pnpm install
cp .env.example .env   # add your OPENAI_API_KEY
pnpm run dev           # http://127.0.0.1:8000
pnpm --filter backend test
```

Quick sanity checks:

```
curl localhost:8000/tools | jq '.tools | length'   # -> 191
curl -X POST localhost:8000/reset                  # -> {"ok": true, "serviceCount": 7, "toolCount": 191}
curl -X POST localhost:8000/chat \
     -H 'content-type: application/json' \
     -d '{"messages":[{"role":"user","content":"hi"}]}'   # -> 501 until you implement it
```

## Testing your solution

We will run our own test suite against your submitted `/chat` endpoint. The
examples in this package are only a starting point and do not cover every
scenario we will check, so write your own tests for routing, multi-step tool
use, ambiguity, failures, and state changes.

`backend/tests/test_solution_example.py` shows the basic structure with one
small greeting test. It is skipped while `/chat` is still the starter stub;
remove the `@unittest.skip` line when you begin implementing, then extend the
file with cases that exercise your design. Run everything with:

```bash
pnpm --filter backend test
```

## CLI

Once the backend is running, you can inspect responses and tool usage from the terminal:

```bash
pnpm run cli
pnpm run cli -- repl
pnpm run cli -- chat "What conversations do I have in Slack?"
pnpm run cli -- tools --service slack
pnpm run cli -- reset
pnpm run cli -- state
```

Inside the REPL, use `:help` to see commands. The most useful ones are `:tools`, `:reset`, `:state`, and `:raw`.

## Deliverables
- Working `POST /chat` implementation. Please submit the helpers folder and the solution.py file with your implementation as a zip file.
- `DESIGN.md`: We do not expect this to be a detailed account of every line of code that you wrote, rather a high-level overview of your approach to the two main challenges: tool routing and orchestration loop quality. What were the options you considered, what did you choose, and why? This is your chance to show your design thinking and communication skills. We ask that you not use AI tools to write this document, as we want to hear your own thought process.
- **A ~5 minute Loom video**, linked at the top of `DESIGN.md`, walking through your solution end-to-end (architecture plus a couple of scenarios running live). Set sharing so anyone with the link can view it.

## FAQs
- Tools are callable in-process: `from backend.main import get_tool_spec; get_tool_spec("slack_list_users").invoke()`. You don't need a separate HTTP `/invoke` endpoint unless you want one.
- `get_openai_tools(names)` returns OpenAI-compatible tool schemas for any subset of the 191 tools. Use this if you want to control which tools the model sees.
