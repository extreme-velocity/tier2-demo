# llm-bridge — test the AI fleet with zero API keys

A tiny OpenAI-compatible HTTP shim over a local/SDK LLM (default install:
`z-ai-web-dev-sdk`). Point the kit's `AI_REVIEW_BASE_URL` at it and the
whole review/sweep pipeline — real prompt assembly, real diff fetching,
real parsing — runs against your local model. Costs nothing, touches
nothing (pair it with `AI_REVIEW_DRY_RUN=1` to also skip posting).

## Run it

```bash
cd scripts/dev/llm-bridge
bun install   # or: npm install
npm start     # listens on 127.0.0.1:8787
```

## Use it

```bash
# from the kit root, against any PR in any repo you can read:
AI_REVIEW_DRY_RUN=1 \
AI_REVIEW_BASE_URL=http://127.0.0.1:8787/v1 \
AI_REVIEW_API_KEY=local-dev AI_REVIEW_MODEL=zai-local \
GITHUB_TOKEN="$PAT" REPO=owner/repo PR_NUMBER=42 \
  python3 scripts/ai_review.py
```

The bridge:

- `POST /v1/chat/completions` — OpenAI request/response shapes; maps the
  OpenAI `system` role to the SDK's system-prompt convention (first
  message, `assistant` role) and ignores `model`/`max_tokens`/
  `temperature` (the SDK doesn't take them).
- `GET /v1/models` — reports one pseudo-model (`zai-local`) so generic
  OpenAI clients can enumerate.
- `GET /healthz` — readiness probe.

Logs every call to stderr (`in=…ch out=…ch …ms`) — useful for seeing how
much of your prompt actually reaches the model.

## What it's for — and what it's NOT for

Validated use (see the ai-velocity-kit repo's `docs/model-matrix.md` for
the full experiment): the
bridge proves the **plumbing** — auth, diff fetch, prompt assembly, retry
logic, output formatting. A weak local model produced a perfectly
contract-compliant review… with one confidently hallucinated finding
(it claimed a file in the diff wasn't in the diff). So:

- ✅ Smoke-test the pipeline before spending API money
- ✅ Prompt-contract iteration (formatting, sections, disclaimer)
- ❌ Judging finding quality — that needs the real model you'll run in CI

## Security

No auth, no rate limit, localhost-only by design. Never expose it beyond
your machine; it executes nothing but it forwards everything.
