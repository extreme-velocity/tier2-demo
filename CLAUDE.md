# CLAUDE.md

Quick-start conventions for Claude Code sessions in this repo. The full
intent layer lives in [AGENTS.md](AGENTS.md) — read it first for
contribution rubric, the Footprint Ladder, and testing rules. This file
only covers Claude-specific workflow.

## Session Start

```bash
# 1. Read the intent layer
#    (AGENTS.md is auto-loaded; also check docs/ADR/ for recent decisions)
# 2. Sync the environment
make dev          # installs python (uv) + typescript (npm) deps
# 3. Run the fast checks before you start editing
make lint test
```

## Workflow Rules

1. **Branch naming:** `fix/…`, `feat/…`, `docs/…`, `test/…`, `refactor/…`.
2. **Conventional commits** — required. The changelog is generated from
   them: `fix(gateway): prevent crash when config is a string`.
3. **One logical change per PR.** If you find a second bug while fixing the
   first, note it in the PR description or open a follow-up issue — don't
   bundle it.
4. **Before "fixing" a missing piece**, verify it's not intentional design:
   `git log -p -S "<symbol>"` to read the original intent.
5. **Run tests before pushing.** CI mirrors `make lint test`; don't push red.
6. **Attribution trailer on every commit you author:**

   ```
   Co-Authored-By: Claude <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_<id>
   ```

   (The session link is optional but valuable — it makes every AI-authored
   commit traceable to the exact conversation that produced it.)

## Commands

Tier note: `make`, release and metrics tooling arrive with the kit's
tier-1 bundle. At tier 0 (or in a repo without them), run the underlying
tools directly (`uv run pytest`, `uvx ruff check`, `npm test`).

| Task | Command |
|------|---------|
| Dev setup | `make dev` |
| Lint + autofix (python) | `make lint` |
| Lint + autofix (ts) | `make lint-ts` |
| Tests | `make test` |
| Release (maintainers) | `python scripts/release.py --part patch` |
| Repo velocity report | `python scripts/repo_metrics.py` |

## Testing Requirements

- Bug fixes REQUIRE a test that fails without the fix.
- Assert invariants, never current values (no change-detector tests).
- E2E for anything touching I/O, config, or auth — real paths, not mocks.
- Tests never write outside temp dirs.

## Review Fleet

Your PRs will be reviewed by an automated reviewer
(`.github/workflows/ai-review.yml`) within minutes. Treat blocking
findings as real work items; reply in the PR when you disagree, with
evidence. A human makes the final merge decision.
