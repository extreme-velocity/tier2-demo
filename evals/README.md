# Evals

Capability evals that gate agent-facing changes. Upstream ships evals for
the core capabilities agents must not regress (browser_use, compaction,
tool reading, schema). Keep evals:

- **Reproducible** — fixed inputs, deterministic scoring where possible
- **Contract-based** — assert relationships that must hold, not
  golden-output snapshots (same rule as unit tests)
- **Cheap enough to run per-PR** on the lane they gate

Suggested layout:

    evals/<capability>/
      README.md        # what the capability must do + scoring rubric
      cases/           # inputs, one case per file
      run.py           # executes cases against current main

Add an eval BEFORE changing behavior an agent depends on.
