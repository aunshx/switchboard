# DESIGN.md

**Loom:** [LINK](https://www.loom.com/share/b933f1cd77794131958c1f69367a16fb)

---

## The problem

There are 191 tools. As OpenAI function schemas that is 76,669 tokens and resent every round of the loop. So, the distribution kills the obvious fix. Looking at the distributiion: github is 86 tools, calendar 29, linear 25, gmail 20, googledrive 20, slack 10, perplexity 1. So, routing to a service still leaves you 86 in the worst case.

Ultimately what the design comes down to is picking a tool and calling a tool need different amounts of information. Picking needs a name and a sentence and calling needs the full schema. Schemas are what blow up context so we only fetch the ones you will actually use.

## Options

**Pass all 191.** 76,669 tokens per round plus the accuracy degradation that the brief warns about.

**Embedding retrieval over descriptions.** My first plan. I dropped it after reading the catalog. The descriptions are one-liners and cosine similarity over one-liners is noisy where it matters and when several tools in a service differ by one verb. A model reading those same one-liners is more accurate and took less time to build.

**Service router only.** Cheap, stable and insufficient. See github.

**Two-stage LLM selection.** What I built. A cheap call sees names and short descriptions for all 191 with no schemas and returns a shortlist and the executor sees only those schemas.

Digest is 3,195 tokens against 76,669. **24.0x.** Exact counts from tiktoken because the chars/4 heuristic I started with said 18.4x and was off by a third.

## What I built

```
query -> selector (gpt-4.1-mini, digest of all 191 names + descriptions)
      -> 8-12 names, validated against the registry
      -> executor (gpt-5-mini, effort=low, sees only those schemas)
      -> dispatch -> ToolSpec.invoke -> tool_calls log
      -> loop until text-only or MAX_ROUNDS=8
```

**`find_tools` escape hatch.** The selector misses and when it does the executor asks for more tools by description and they get injected next round. Its not logged in `tool_calls` since it is not a registered name and padding that log works against the scoring criterion. and is counted internally.

**Gated re-selection.** Cross-service work needs tools the first pass did not anticipate so selection reruns on round 1 after a tool error or when `find_tools` fires and unions rather than replaces. Also, running it every round cost 6.6s of a 17.7s turn and added nothing after round 1.

**Validation drops invented names.** Case-only mismatches get repaired and counted separately since those are different signals. First is cosmetic and the other one is a routing error and this step mattered more than I expected, see below.

**Failure containment.** An upstream API error used to 500 and take the `tool_calls` log with it. That log is the scored artifact so losing it turns a partial success into a zero and now it returns 200 with the log intact and says what completed. Selector failure degrades the same way.

## Results

29/30 across three runs of a ten-case suite: no-tool, single-tool, sequential cross-service write, unsatisfiable search, missing capability, parallel reads, ambiguous parameters, error recovery, out of scope, Perplexity.

| | |
|---|---|
| Selection recall | 1.00, zero variance |
| Selection precision | 0.13 |
| Tool calls | 11.3 mean vs minimum 10 |
| Wall p50 / max | 9.5s / 17.6s |

Precision of 0.13 is on purpose. The shortlist is 8 to 12 when most queries need one or two and that margin buys the recall as exposed tools cost input tokens and uncalled tools cost nothing on the metric the brief names so I would rather over-expose and call the minimum.

## What measuring changed

Four things I built or assumed were wrong

**Parallel read dispatch bought nothing.** There Two mock reads: 0.029ms serial, 0.090ms threaded. Pool setup costs 3x the work and these mocks are in-process dict lookups so tool execution is 0.0002% of a turn and wall clock is LLM latency. End to end it is11,734ms serial against 11,805ms parallel. Code, allowlist and tests are all still there behind `PARALLEL_READS` which are defaulted off. I am not shipping a thread pool over unlocked process-global state for zero measured gain. So against real MCP servers over a network the structure is right and the flag flips.

**The read-only allowlist could not be built by naming convention.** I verified it with a `GET /state` sha256 diff around each call instead of trusting names, which caught three writes with read-shaped names: `github_mark_all_notifications_read`, `GOOGLECALENDAR_CALENDAR_LIST_INSERT`, `GOOGLECALENDAR_CALENDAR_LIST_UPDATE`. `perplexity_search` is out too and it increments a query counter. The convention would have shipped a bug.

**The dedup cache fires zero times.** I added a turn-scoped cache keyed on tool name plus args to cut the redundant calls I was seeing. Zero hits across ten cases. The redundant calls are never argument-identical. One case issues two Gmail fetches with different queries, `timelines` then `timeline OR timelines` which is a deliberate broadening retry. Another probes four filename variants. LLM redundancy is rephrased so exact-argument matching cannot collapse it and it stays as a safety net against verbatim repetition but a per-tool-per-turn budget is the actual lever.

**Validation is what makes the cheap selector usable.**

| Selector | Pass | Recall | Selector p50 | Wall p50 | Invented names |
|---|---|---|---|---|---|
| gpt-5-nano | 20/20 | 1.00 | 18,142ms | 25,684ms | 5 |
| **gpt-4.1-mini** | 19/20 | 1.00 | **1,796ms** | **9,510ms** | 20 |
| gpt-5-mini | 20/20 | 1.00 | 8,390ms | 17,414ms | 0 |

Recall is 1.00 for all three so accuracy is not the differentiator at this catalog size and latency is and gpt-4.1-mini is 4.7x faster than nano at the selector step and roughly halves end-to-end.

Looking at the last column gpt-5-mini invented zero tool names in twenty cases whereas gpt-4.1-mini invented twenty about one per case. The drop step is what lets me run the fast cheap model without handing the executor a fabricated tool.

Talking about ywo smaller results, gpt-5-nano is the slowest of the three because it is a reasoning model running at default effort on a task that needs none and on the executor, dropping effort from default to low took a round from 2,472ms to 1,250ms with an identical correct call.

**`find_tools` did nothing until the prompt said it existed.** With a deliberately crippled selection the model silently dropped half of a two-part request instead of reaching for the hatch. It needed the system prompt to say its tool list was a shortlist and that finding something and then posting it is not done until the posting happens. Which makes sense as wiring a capability is not the same as making it reachable.

## Two of the four example queries are unsatisfiable

I checked the brief's examples against the fixture.

Nothing in Gmail or Slack matches "timelines". There are no such email, no such channel and Drive has 20 tools, none of which delete a file. There is `delete_comment`, `delete_drive`, `delete_permission`, `delete_reply`, `empty_trash`. There is no file delete and no trash.

I read that as deliberate as the system searches finds nothing and asks, with `GET /state` byte-identical to post-reset in every run. Nothing is invented and nothing is written. The selector reaches for `GOOGLEDRIVE_DELETE_FILE` on every single run, which is the hallucination validation exists to catch. The system prompt now separates "the item does not exist" from "no tool can do this" and has to say which.

## Weaknesses

Case 05 fails 1 in 3. In every run it attempted no write and left `/state` clean. What fails is the phrasing: one run said it could not find the file without naming the capability gap. The behaviour is stable but the reporting is not in this case.

There's no confirmation gate on destructive operations and a delete that a tool supports would just run.

The executor is about 80% of wall clock. The selector is 1.8s of 9.5s, so more routing work moves the number very little and the prefix gets resent every round.

Selector variance on ambiguous queries. "Meeting with everyone on the project" returned Linear tools on one run, pure calendar on another. The recall survives because both supersets contain what is needed but it is real.

## With another 8 hours

Semantic dedup, or just telling the model in-context what it already searched for. Cheaper than either is a per-tool-per-turn call budget.

Lower reasoning effort on gpt-5-* selectors. My own sweep flagged this and I held config fixed rather than tuning mid-measurement. Nano may be competitive once it stops reasoning about a task that needs none.

Skip the selector on conversational turns. "Hello!" pays a full selector call today. So detecting that cheaply is the hard part.

A confirmation gate on writes which is built from an explicit destructive-operation list rather than the read-only allowlist read backwards.

Hybrid retrieval: embeddings to a top 40, LLM reranking to 12. At 191 tools the LLM alone wins. Past a few thousand the digest stops fitting and this becomes necessary.

Eval regression tracking in CI so a prompt change that costs two points of recall fails a build instead of surfacing in a demo.

## Appendix: scaffold notes

Things that cost me time

`get_openai_tools()` emits Responses API shape, not Chat Completions. `ToolSpec.invoke` returns an envelope and the payload sits one level down at `.result`. `_openai_tool_entry` uses the verbose generated docstring as the description, so the short field for the selector digest has to come from `get_tool_catalog()`. `_combined_registry()` rebuilds all 191 entries on every `get_tool_spec` call. Mock state is a process-global singleton with no locking and `_next_ts` / `_next_id` are read-modify-write. Importing `backend.main` from a helper creates a circular import that only fails when the real server starts, never in tests that import the helper directly.

Last one: I assumed strict mode would reject the 632 `default` keys in these schemas and planned a transform ladder for it. So an eight-minute spike proved it accepts them as-is and so I deleted the ladder before writing it.