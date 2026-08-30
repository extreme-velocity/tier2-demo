# Security Policy

## Supported Versions

Only the latest release line receives security fixes.

## Reporting a Vulnerability

**Do not open a public issue.**

Report privately via [GitHub Security Advisories](https://github.com/OWNER/REPO/security/advisories/new)
("Report a vulnerability"). Include reproduction steps and impact
assessment. You will get an acknowledgment within 72 hours.

## Supply-Chain Hardening (what this repo already does)

This template ships with the following protections — keep them intact
when you fork it:

- **Pinned action SHAs** — every `uses:` in `.github/workflows/` pins a
  full commit SHA, not a mutable tag.
- **Least-privilege tokens** — `permissions:` blocks on every workflow;
  unprivileged jobs never hold write tokens.
- **Two-job split for code-executing automation** — linters/fixers run
  unprivileged and emit a patch; a privileged job applies the patch
  without executing repo code (see `autofix.yml`).
- **No secrets in PR-triggered workflows** — trusted automation lives in
  its own workflows behind protected environments; `pull_request`
  workflows get `contents: read` only.
- **Short-lived GitHub App tokens** for privileged automation (1-hour
  TTL installation tokens instead of long-lived PATs) — see
  `.github/actions/get-app-token/` (ships inert — wire it into your
  privileged workflows when you create an App; nothing calls it by default).
- **Dependency scanning** — Dependabot alerts + weekly version bumps.

## CI Security Rules for Contributors

If your PR touches `.github/`:

1. The `ci-reviewed` label gate requires a maintainer to explicitly
   review the workflow change before CI-sensitive jobs pass.
2. Never add `secrets: inherit` to a workflow that runs PR code.
3. Never move privileged operations into `pull_request`-triggered
   workflows — put them in `workflow_run` (which reads config from main,
   not the PR head) or a protected-environment workflow.
