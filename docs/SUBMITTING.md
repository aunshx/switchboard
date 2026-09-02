# How to submit

This page lives at the root of the package as `SUBMITTING.md`. It tells you exactly what to send back and how to package it.

## What you send back

A single archive (`.zip` or `.tar.gz`) containing the **same directory tree we sent you**, with your implementation merged in. The archive should unzip into a folder that looks like:

```
your-submission/
├── README.md              ← unchanged from what we sent
├── DESIGN.md              ← NEW — written by you, one page
├── backend/               ← modified by you
│   ├── main.py            ← your POST /chat lives here
│   ├── (any new modules you added, e.g. backend/router.py)
│   └── tests/             ← if you added tests, leave them here
├── docs/                  ← unchanged
├── .env.example
├── .gitignore
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
└── turbo.json
```

## What to leave OUT of the archive

- `node_modules/`
- `backend/.venv/` (or any other virtualenv)
- `__pycache__/`, `.turbo/`, `.idea/`, `.DS_Store`
- Any `.env` containing secrets (use `.env.example` if you want to document required variables)

A clean archive should be **well under 5 MB**. If yours is bigger, you probably included an environment by accident.

## Required deliverables

1. **Working `POST /chat`** in `backend/main.py`. The endpoint must accept and return the documented payload (see the main README). All tool calls made during a turn must appear in the response's `tool_calls` log.
2. **`DESIGN.md`** at the repo root. One page covering:
   - Your tool-routing strategy (and why).
   - The orchestration loop structure (when does it stop, how errors propagate, parallel vs. sequential).
   - What you'd do with another 8 hours.
   - **A link to a ~5 minute [Loom](https://www.loom.com) video** walking through
     your solution end-to-end (architecture + a couple of scenarios running live).
     Put the link at the top of `DESIGN.md`. Make sure sharing is set so anyone
     with the link can view it — we can't grade a video we can't open.

## Optional but appreciated

- Any extra tests you added in `backend/tests/`.
- Notes in `DESIGN.md` on tradeoffs you considered and discarded.

## How to submit

Run `submit.py` with the case-study link we sent you — the one that looks like
`https://portal.instalily.ai/case-study/abcde`. Paste it exactly as given; the
script reads your submission id from that link, zips your working copy
(excluding `node_modules/`, virtualenvs, caches, etc.), and uploads it to the
grader:

```bash
cd /path/to/your-working-copy
python submit.py https://portal.instalily.ai/case-study/abcde
```

That's the whole flow — no endpoint or id to pass separately. Useful flags:

```bash
python submit.py <your-link> --zip-only          # build submission.zip, don't upload
python submit.py <your-link> --zip path/to.zip   # upload an existing archive
```

If you'd rather package by hand, the equivalent archive is:

```bash
zip -r ../submission.zip . \
    -x '**/node_modules/*' \
       '**/.venv/*' \
       '**/__pycache__/*' \
       '**/.turbo/*' \
       '**/.idea/*' \
       '**/.env'
```

then upload it with `python submit.py <your-link> --zip ../submission.zip`.

## What we'll do with it

We run an automated grading process that:

1. Unzips your archive.
2. Creates a clean Python virtualenv and installs `backend/`.
3. Boots `uvicorn backend.main:app` on a private port.
4. Waits for `GET /health` to return 200.
5. Posts ~30 scenarios to your `/chat`, resetting state with `POST /reset` between each and reading `GET /state` afterward to verify the end-state.
6. Records pass/fail correctness per scenario, plus wall-clock latency and tool-call counts (tracked, not graded).

The harness exits non-zero if any scenario fails its correctness checks; latency and tool-call counts are tracked but never fail you. We do a human read of your `DESIGN.md` and code structure separately, but the scorecard is the objective baseline.

## Sanity check before you send

Run these against your own server. If any of them fails, fix it before submitting.

```bash
pnpm run dev                                               # server boots, no exceptions
curl localhost:8000/tools | jq '.tools | length'           # -> 191
curl -X POST localhost:8000/reset                          # -> {"ok": true, ...}
curl -X POST localhost:8000/chat \
     -H 'content-type: application/json' \
     -d '{"messages":[{"role":"user","content":"What conversations do I have in Slack?"}]}'
                                                           # -> 200 with assistant message and tool_calls populated
pnpm --filter backend test                                 # the 56 existing tests still pass
```
