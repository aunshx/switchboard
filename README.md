# Switchboard

A tool router and orchestration loop for a workspace of **191 tools** across seven
services — Gmail, Google Calendar, Google Drive, Slack, Linear, GitHub and Perplexity.

Switchboard implements `POST /chat`: it takes a user message, decides which handful of
the 191 tools the model should be allowed to see, runs a multi-round tool-calling loop
against them, and returns the assistant's answer plus a complete log of every tool call
it made.

The name is the idea. Picking a tool and calling a tool need different amounts of
information: picking needs a name and a sentence, calling needs the full JSON schema.
Schemas are what blow up context, so Switchboard patches through only the lines that
are actually going to carry traffic.

## Why it is not just "pass all the tools"

| | Tokens |
|---|---|
| All 191 tools as OpenAI function schemas | 76,669 |
| Catalog digest (`name \| service \| description`) | 3,195 |

**24x.** And that full-schema cost is paid *every round* of the loop, on top of the
tool-selection accuracy degradation that comes with a 191-way choice.

Routing by service does not save you either: GitHub alone is 86 tools, Calendar 29,
Linear 25, Gmail 20, Drive 20, Slack 10, Perplexity 1. The worst case is still 86.

## How it works

```
query ─▶ selector  (gpt-4.1-mini, sees the digest of all 191 names + descriptions)
      ─▶ 8–12 tool names, validated against the registry
      ─▶ executor  (gpt-5-mini, effort=low, sees only those schemas)
      ─▶ dispatch ─▶ ToolSpec.invoke ─▶ tool_calls log
      ─▶ loop until text-only answer, or MAX_ROUNDS = 8
```

- **`find_tools` escape hatch.** The selector sometimes misses. When it does, the
  executor asks for more capability in plain words and the matching tools are injected
  for the next round.
- **Gated re-selection.** Selection reruns after round 1 only on a tool error or a
  `find_tools` call, and unions with the current shortlist rather than replacing it.
  Running it every round cost 6.6s of a 17.7s turn and added nothing.
- **Name validation.** Invented tool names are dropped; case-only mismatches are
  repaired. The two are counted separately — one is cosmetic, the other is a routing error.
- **Failure containment.** An upstream API error returns 200 with the `tool_calls` log
  intact rather than 500-ing and taking the scored artifact with it.

Full reasoning, the options considered and the measurements are in
[`DESIGN.md`](DESIGN.md).

## Results

29/30 across three runs of a ten-case suite covering no-tool, single-tool, sequential
cross-service writes, unsatisfiable search, missing capability, parallel reads,
ambiguous parameters, error recovery, out-of-scope and Perplexity.

| | |
|---|---|
| Selection recall | 1.00, zero variance |
| Selection precision | 0.13 (deliberate — see DESIGN.md) |
| Tool calls | 11.3 mean vs. minimum 10 |
| Wall clock p50 / max | 9.5s / 17.6s |

## Layout

```
backend/
  solution.py          the /chat orchestration loop
  helpers/
    catalog.py         registry, digest, name validation
    selector.py        stage-one tool selection
    dispatch.py        one invocation path, one log
    config.py          models, round caps, feature flags
  main.py              FastAPI wiring (given)
  tooling.py           ToolSpec (given)
  *_mock/              the seven mock services, 191 tools (given)
  tests/               mock suites, dispatch tests, local eval harness
docs/CASE_STUDY.md     the original brief
DESIGN.md              the write-up
```

## Running it

```bash
pnpm install
cp .env.example .env          # add your OPENAI_API_KEY
pnpm run dev                  # http://127.0.0.1:8000
pnpm --filter backend test
```

```bash
curl localhost:8000/tools | jq '.tools | length'   # -> 191
curl -X POST localhost:8000/chat \
     -H 'content-type: application/json' \
     -d '{"messages":[{"role":"user","content":"What conversations do I have in Slack?"}]}'
```

There is a CLI for poking at it from the terminal:

```bash
pnpm run cli -- chat "What conversations do I have in Slack?"
pnpm run cli -- repl
pnpm run cli -- tools --service slack
pnpm run cli -- reset
pnpm run cli -- state
```
