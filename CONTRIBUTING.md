# Contributing

Thanks for contributing! This guide has one goal: **get good changes merged
fast** — the project runs a high-velocity pipeline (median PR merge time
target: under 1 hour; the upstream project that inspired this template
runs at 22 minutes). You can help by aiming your contribution at the
target described in [AGENTS.md](AGENTS.md), which is the intent layer for
both human reviewers and the automated review fleet.

## The Short Version

1. **Search first.** Existing PRs and issues — duplicates are the top
   source of closed-without-merge PRs.
2. **Small, focused PRs.** One logical change. Median merged PR upstream:
   151 lines across 3 files. Small PRs merge in minutes; big ones wait.
3. **Conventional commits** — `fix(scope): …`, `feat(scope): …`. The
   changelog is generated from these.
4. **Verify your premise before fixing.** Reproduce the bug on current
   `main`; check the code's original intent (`git log -p -S "<symbol>"`)
   — the "missing" behavior may be intentional design.
5. **Tests assert invariants, not snapshots.** A test that freezes a
   current value will be deleted; a test that states a relationship that
   must hold will live forever.

## Development Setup

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
make dev        # python (uv sync) + typescript (npm ci)
make test       # full local gate — same as CI
```

## Branch & Commit Conventions

```
fix/description        # Bug fixes
feat/description       # New features
docs/description       # Documentation
test/description       # Tests
refactor/description   # Restructuring (no behavior change)
```

Commit types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`,
`perf`, `ci`, `revert` — with a scope when it helps: `fix(gateway): …`.

## What Happens After You Open a PR

1. **CI lanes run only what your diff touches** (a docs-only PR takes
   seconds). The aggregate `All required checks pass` gate is the only
   check you need to see green.
2. **An automated AI review lands within minutes** — it's advisory ("AI
   code review — automated review for reference"), marked blocking /
   important / nit. Respond to blocking findings or push back with
   evidence in the PR.
3. **A human merges.** Bots never approve or merge community PRs.
4. **If your fix was already implemented on main**, the triage sweeper
   may close your PR with the implementing commit cited — your report
   still helped. If your work informed a fix, the maintainers salvage
   your authorship via rebase-merge so the credit stays in git history.

## Issue Triage

Issues are labeled by automation (`type/*`, `comp/*`, `P1–P3`) and closed
only on verified grounds: already implemented, not reproducible, or
incoherent. If your issue gets closed and you disagree, reply with new
evidence — closed items reopen all the time.

## Security

Do not open public issues for security problems — see [SECURITY.md](SECURITY.md).
