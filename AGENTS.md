# AGENTS.md — Development Guide (for AI coding assistants AND humans)

> This file is the **intent layer** of the repository. It is written for two
> audiences at once: human contributors and the AI agents (Claude Code,
> Codex, Cursor, Copilot, review bots, triage sweepers) that work on this
> repo. Everything an automated reviewer is allowed — and not allowed — to
> decide lives here.
>
> **Inspired by NousResearch/hermes-agent's 96KB AGENTS.md** — the operating
> manual behind 175 commits/day with a 22-minute median merge time. This
> template distills the parts that transfer to any repo. Delete what doesn't
> apply; keep the structure.

**Never give up on the right solution.**

## What This Repo Is

<!-- One paragraph: what the product does, the surfaces it runs on, and the
two or three design invariants that shape every decision. AI reviewers need
this to judge whether a change fights the design. -->

<PROJECT_NAME> is <one-line description>. It runs the same core across
<surfaces: CLI / API / web / desktop / bots>. It is extended primarily
through **plugins and skills**, not by growing the core.

Two properties shape almost every design decision:

- **<INVARIANT_1>** — <why it's sacred, what breaks it, why that costs users money/trust.>
- **The core is a narrow waist; capability lives at the edges.** Every
  addition to the core is paid for on every call/launch. Most new capability
  should arrive as <cheaper extension points>, not as core surface.

## Contribution Rubric — What We Want / What We Don't

This is the project's intent layer. Use it two ways:

1. **For humans and agents doing the work** — what gets merged, what gets
   rejected, so a contribution aims at the target.
2. **For automated review (the triage sweeper)** — guidance on when an item
   is safe to close on the allowed reasons and, just as important, **when
   NOT to close**. Taste-based "we don't want this" closes are NOT an
   automated decision — those stay with a human maintainer.

### What we want

- **Fix real bugs, well.** The bulk of what lands is `fix(...)` against an
  actual reported symptom. A good fix reproduces the symptom on current
  `main`, points to the exact line, and fixes the whole bug class — sibling
  call paths included.
- **Expand reach at the edges.** New integrations, adapters, UI features
  are welcome, including large ones — as long as they integrate with
  existing UX rather than bolting on raw env vars.
- **Refactor god-files into clean modules.** Declared refactors with huge
  mechanical diffs merge routinely. The "every line traces to the request"
  test applies to *feature* PRs; a declared refactor's request IS the
  extraction.
- **Behavior contracts over snapshots.** Tests assert how two pieces of
  data must relate (invariants), never freeze a current value. See
  "Don't write change-detector tests."
- **E2E validation, not just green unit mocks.** For anything touching I/O,
  config propagation, or security boundaries, exercise the real path. Mocks
  hide integration bugs.
- **Contributor credit preserved.** Salvage external work by cherry-picking
  (rebase-merge) so authorship survives in git history; don't reimplement
  from scratch when you can build on top.

### What we don't want (rejected even when well-built)

- **Speculative infrastructure.** Hooks/extension points with no concrete
  consumer. Adding a hook is easy; removing one after plugins depend on it
  is hard.
- **Config escape hatches.** Env vars for non-secret config (all behavioral
  settings belong in the config file; env is for credentials only).
- **"Fixes" that destroy the feature they secure.** Read the original
  commit's intent (`git log -p -S "<symbol>"`) before restricting behavior.
- **Telemetry without opt-in gating.** No analytics until a user-facing
  opt-in exists. Park behind a label; do not merge.
- **Third-party products integrated into the core tree.** They impose
  maintenance burden on a fast-moving core for a backend we don't own. Ship
  as a standalone plugin repo; promote in community channels.

### Before you call it a bug — verify the premise (and when NOT to close)

The most common reason a well-written PR gets closed is not code quality —
it is that the change is built on a **wrong premise** or treats
**intentional design as a gap**. These cut both ways: they tell a human
reviewer what to scrutinize, and tell the automated sweeper when an item is
NOT safe to close (when in doubt, leave it open for a human).

- **"Intentional design, not a gap."** A limitation that looks like an
  oversight is often deliberate. Ask whether the isolation IS the design.
- **"The premise doesn't hold against how X actually works."** Trace the
  real code before accepting the rationale. If you can't point to the exact
  line where the bug manifests AND show the fix changes that line's
  behavior, you haven't verified the premise.
- **"This fix was wrong — the omission was deliberate."** Adding the
  obvious-looking missing piece can break things the omission protected.
  The absence may be load-bearing.
- **"Overreached / resurrected an approach we'd moved past."** Scope creep
  beyond an agreed base gets rejected even when the code works.

The throughline: **verify the claim AND the intent against the codebase
before writing or merging a fix.** A confirmed reproduction plus a
line-level account of where the fix acts beats a plausible rationale every
time.

### The Footprint Ladder (new capability decision)

Each rung adds more permanent surface. Choose the highest (least-footprint)
rung that correctly solves the problem:

1. **Extend existing code** — variation of something that exists. Zero new surface.
2. **CLI command + skill/doc** — expressible as shell commands guided by a doc. Zero framework footprint.
3. **Gated tool/module** — structured params AND only appears when a prerequisite is configured.
4. **Plugin** — third-party/niche capability that doesn't ship in core.
5. **External service integration** — built as its own repo/package.
6. **New core surface** — last resort; only when broadly useful to nearly every user.

When 3+ open PRs try to integrate the same *category* of thing, don't merge
them one at a time — design an interface, wrap the existing built-in as the
first provider, and turn the competing PRs into plugins against it.

## Development Environment

```bash
# Python side
cd python && uv sync && uv run pytest -q
# TypeScript side
cd typescript && npm ci && npm test
# Everything
make test
```

## Project Structure

```
<repo>/
├── python/            # Python package (uv + ruff + pytest)   ← example lanes;
├── typescript/        # TS package (npm + vitest + biome)      keep the ones you use
├── scripts/           # Automation: release.py, ai_review.py, sweeper.py, repo_metrics.py
├── prompts/           # System prompts for the AI fleet (reviewer, sweeper)
├── evals/             # Capability evals that gate agent-facing changes
├── contributors/      # Email → login attribution maps + maintainers.txt roster
├── docs/              # ADRs, playbooks, analysis
└── .github/           # CI lanes, AI review, autofix, gates, templates
```

File counts shift constantly — the canonical source is the filesystem.
Directories listed here may not exist yet at your adoption tier (see the
kit's tier docs) — the structure describes the destination, not day one.

## Commit & PR Conventions (enforced)

- **Conventional Commits** — `fix(scope):`, `feat(scope):`, `docs:`,
  `test:`, `refactor:`, `chore:`, `perf:`, `ci:`, `revert:`. ~90% of merged
  PRs follow this; the release tooling depends on it for changelogs.
- **One logical change per PR.** Don't mix a bug fix with a refactor.
- **Branch naming:** `fix/…`, `feat/…`, `docs/…`, `test/…`, `refactor/…`.
- **PR description must state:** what changed and why, how to test it, what
  platforms you tested on.

## Configuration Doctrine

Behavioral settings live in the config file; **env vars are for
credentials only**. The test both ways: if a setting changes behavior,
it belongs in config (reviewable, documented, typed); if it authenticates,
it belongs in env (secret, injectable). This keeps config reviewable in
PRs — an env var that silently changes behavior is an unaudited code
path.

- Every new config option: document it in the same PR that adds it.
- Never read a secret from the config file; never read behavior from env.

## Dependency Pinning Policy

Every dependency gets an upper bound to limit supply-chain blast radius
(born upstream from the litellm compromise, reinforced by the May 2026
worm campaign):

| Source | Rule | Example |
|---|---|---|
| Package (post-1.0) | `>=floor,<next_major` | `httpx>=0.28.1,<1` |
| Package (pre-1.0) | `>=floor,<minor+2` | `>=0.29,<0.32` |
| Git URLs | pin the commit SHA | `git+https://…@<40-char-sha>` |
| GitHub Actions | SHA + version comment | `uses: actions/checkout@<sha> # v4.2.2` |
| CI-only tools | exact pin | `pyyaml==6.0.2` |

A bare `>=X.Y.Z` with no ceiling fails review — a hijacked release must
not be able to walk into main through a routine bump.

## Attribution & Credit

- **Contributor credit is sacred.** When superseding or re-implementing
  someone's work, rebase-merge with re-authored commits so their name
  lands in git history — don't paste their diff into a clean PR.
- Commit-author emails map to GitHub logins in `contributors/emails/`
  (one file per email — additions never conflict; a shared dict did,
  constantly). The attribution CI gate enforces the map.
- AI agents authoring commits: add a trailer
  (`Co-Authored-By: Claude <noreply@anthropic.com>` or your model's
  equivalent) and, where supported, a session link — upstream's
  traceability pattern: the commit points at the exact conversation that
  produced it. Trailers measure *direct* agent commits; fleet accounts
  measure the rest.

## Testing Rules

- **No change-detector tests.** Assert invariants (relationships that must
  hold), not current values (model lists, counts, literals) — those break
  on every legitimate change.
- **Tests must not write outside temp dirs** — never touch the user's home
  or the repo root.
- **Never fake the host OS** — don't monkeypatch `sys.platform`; use markers
  and run on the real OS matrix.
- **Never read source code in tests** — test behavior, not implementation.
- **Where to place what:** unit tests next to the module or in `tests/`;
  cross-cutting E2E tests in `tests/e2e/`.

## Important Policies

- **<POLICY: e.g. "Prompt caching must not break">** — <the invariant, how
  to check it, what tests prove it>.
- **Background process notifications** — anything that spawns long-lived
  work must surface completion/failure to the user, not just log it.

## Known Pitfalls

<!-- Distilled from real incidents. Every entry earns its place by having
caused an actual bug. This section is the highest-value thing you can
maintain for AI agents — it encodes scar tissue. -->

- **Squash merges from stale branches silently revert recent fixes** —
  rebase before merging; the history-check workflow guards this.
- **Don't infer process identity from argv substrings.**
- **Don't hardcode paths** — everything resolves through the config layer.
- **Never gate session capability on process env vars.** If a feature
  depends on *who is on the other end of the connection* (a UI, a
  client), resolve it from the session, not from an env var on the
  server process — the env var only holds on the topology where you
  spawned both halves, and fails invisibly everywhere else.
- **<YOUR_INCIDENT_HERE>** — replace this entry with the first real bug
  this repo's automation catches. Keep the format: symptom, root cause,
  the rule that now prevents it.

## For AI Agents Working On This Repo

- Read this file fully before proposing changes. Check the Footprint Ladder
  before adding any new surface.
- Verify premises against the code (`git log -p -S`) before "fixing"
  anything that looks like a missing piece.
- When you author commits, include attribution trailers:
  `Co-Authored-By: Claude <noreply@anthropic.com>` (or your model's
  equivalent). Where supported, include the session link for traceability.
- The automated review fleet (see `.github/workflows/ai-review.yml` and
  `prompts/`) posts comments on your PRs. "AI code review — automated
  review for reference" comments are advisory; a human makes the final
  call. Respond to blocking findings before requesting re-review.
- You may NOT approve or merge your own PRs. Self-approval by agents is
  forbidden; the merge queue requires a human or a delegated maintainer
  account.
