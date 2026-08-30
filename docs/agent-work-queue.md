# Agent Work Queue (Kanban protocol)

> The multi-agent work-queue pattern distilled from hermes-agent's Kanban
> system (SQLite-backed board; claim/heartbeat/review-lanes; failure-limit
> circuit breakers). When you run more than one coding agent at a time —
> Claude Code + Codex workers on parallel tasks — ad-hoc terminal juggling
> breaks by the third agent. A durable board with claim semantics does not.

## The protocol (file-based, zero infrastructure)

Create a `kanban/` directory in your repo. One markdown file per task,
named `NNN-slug.md` (monotonic number). The file IS the task record:

```markdown
---
id: 042
title: Fix trailing-dash bug in slugify
status: in-progress        # open | in-progress | review | done | blocked
claim: agent-a             # who owns it now
heartbeat: 2026-08-31T14:05Z   # updated by the owner every few minutes
attempts: 1                # failed attempt count (circuit breaker)
priority: P1
created: 2026-08-31T13:50Z
---

## Task
Reproduce + fix the trailing-dash bug reported in #12.

## Acceptance
- failing-first test
- fix in python/src/aikit/slugs.py
- all lanes green
```

## Rules of the road (enforced by convention, checked by agents)

1. **Claim before work.** Read the board, pick an `open` task, atomically
   set `status: in-progress` + `claim: <your-agent-id>` + a fresh
   `heartbeat` in the same commit. Two agents never work one task.
2. **Heartbeat or lose the claim.** Any agent may reclaim a task whose
   heartbeat is stale (>30 min): set `claim` to yourself, note the
   takeover in the task body. Stale claims are how crashed workers get
   cleaned up without a human.
3. **Circuit breaker.** On failure, increment `attempts`. At
   `attempts: 2`, set `status: blocked` — a human decides. This is the
   single most important rule: it stops a confused agent from burning
   your API budget in a spin loop (upstream default: 2).
4. **Review lane.** Completed work moves to `status: review` and opens a
   PR (the normal CI + advisory-AI-review pipeline applies). The task is
   `done` only when merged — the board tracks work, the repo tracks truth.
5. **Blocking graph.** A task may list `blocked-by: [041]`. Agents pick
   only unblocked `open` tasks; humans resolve the blockers.
6. **Never edit another agent's in-flight task file** — only heartbeat
   takeover (rule 2) or review transitions after `status: review`.

## What this buys you

- **Durable state**: the board survives terminal crashes, context
  exhaustion, and session handoffs — it's just files in git.
- **Parallel agents without collisions**: claims serialize access.
- **A trail**: every task file is an audit record of what was attempted,
  by which agent, with what outcome.

## When to graduate past files

File-based boards race when two agents commit simultaneously — the
`heartbeat` convention resolves most conflicts, but if you're running
5+ workers, move to the upstream design: SQLite board + a dispatcher
loop (reclaim stale claims, promote ready tasks, spawn workers) + a
toolset so worker agents get `kanban_*` tools with zero schema footprint.
The protocol above translates 1:1 (columns become a `status` column;
`attempts` becomes the failure-limit counter).
