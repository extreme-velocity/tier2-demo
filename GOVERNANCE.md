# Governance

How this project is run as it grows — written **before** the growth,
based on the scaling path of a repo that went 0 → 238K stars in 13 months.
Adopt the stages as your community hits them; skip nothing when you get
there.

## Stage 0 — Internal / Pre-Launch (you are here)

- Private repo, small team + AI agents. Everything in this kit is
  already sized for this stage: lane-based CI, advisory AI review,
  conventional commits, attribution trailers.
- **Decisions**: record them in `docs/ADR/` from day one. An ADR is
  10 minutes now or an hour-long archaeology session in six months.
- **The intent layer (`AGENTS.md`) is maintained like code** — every
  rejected-then-recurring pattern gets added to the rubric.

## Stage 1 — Launch

- Add: CODE_OF_CONDUCT.md, SECURITY.md contact, Discussions (move Q&A
  out of Issues), the `good first issue` + `help wanted` labels.
- Turn on the **triage sweeper early** — the moment inbound exceeds
  ~20 items/week, human triage becomes the bottleneck. Start with
  `verdict: label-only` mode (no closes) for 2 weeks, audit its labels,
  then enable limited closes (max 10/run, high confidence only).
- **Issue templates with mandatory reproduction fields** — the single
  biggest lever on triage cost. Vague reports can't be verified, and
  unverifiable reports can't be closed by automation either.

## Stage 2 — Community at Scale (100+ contributors)

- **Branch protection:** require `All required checks pass` (the
  aggregate gate), `signed commits` recommended, no required approvals
  for docs-only lanes; core code requires 1 human approval + advisory AI
  review responded-to.
- **Maintainer roster**: publish who can merge what. Every automated
  close is attributable to a human-owned policy (the sweeper executes
  policy; it doesn't set policy).
- **Salvage protocol** (see `contributors/emails/`): when re-implementing
  community work, rebase-merge with re-authored commits so the original
  reporter's identity survives in git history. The attribution check
  workflow enforces the email map.
- **Plugin ecosystem**: resist third-party products entering the core
  tree. Publish a plugin template + registry instead. Upstream, this
  single policy prevented dozens of unmaintainable vendor integrations.

## Stage 3 — Ecosystem (this is where hermes-agent operates)

- **AI fleet with dedicated identities**: reviewer account, triage
  account, autofix GitHub App. Each posts with explicit self-labeling
  ("AI code review — automated review for reference") and HTML markers
  for idempotency.
- **Cluster detection**: the sweeper groups duplicate/competing
  contributions and routes the decision to a maintainer.
- **Multi-language docs** (upstream: ES, zh-CN, ur-PK) — translated
  READMEs roughly doubled international adoption.
- **Governed automation budget**: scheduled workflows live behind
  protected environments with short-lived App tokens; the sweeper has a
  circuit breaker (max closes per run); every workflow documents the
  incident that justifies its existence.

## Automation Bill of Rights (for humans in the loop)

1. Every automated action leaves an audit trail (marker comment + label
   with the reason).
2. Every automated close cites evidence (commit SHA, failed repro steps).
3. Humans can always reopen; reopening is never penalized.
4. Taste-based decisions ("won't implement") belong to humans. Always.
5. Automation that closes things has a kill switch (disable the
   workflow; items reopenable in bulk).
