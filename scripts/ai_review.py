#!/usr/bin/env python3
"""AI PR reviewer — provider-agnostic (OpenAI-compatible endpoint).

Posts one advisory review comment per PR head SHA. Idempotent: if a
review for this SHA already exists, skips (the per-SHA history is the
audit trail; re-pushed PRs get a fresh review).

Env:
  GITHUB_TOKEN         token with pull-requests:write
  AI_REVIEW_API_KEY    provider API key
  AI_REVIEW_BASE_URL   default https://api.openai.com/v1
  AI_REVIEW_MODEL      default gpt-4o
  AI_REVIEW_MAX_TOKENS default 4000 (raise if reviews truncate)
  PR_NUMBER, REPO      target
  AI_REVIEW_DRY_RUN    set to 1 to print the review instead of posting it
                       (prompt/model testing without touching the PR — use
                       this to evaluate models before wiring a key)
"""

import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"


def gh(path, token, method="GET", payload=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-review",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def get_diff(repo, number, token):
    req = urllib.request.Request(
        f"{API}/repos/{repo}/pulls/{number}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
            "User-Agent": "ai-review",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def llm(system, user, base_url, api_key, model, max_tokens=4000):
    """One chat completion with retry/backoff on 429 + 5xx.

    Free-tier and shared-pool providers (OpenRouter :free models) return
    429s routinely; a single retry with backoff converts most failures
    into successes without masking hard errors (4xx bubbles up).
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    attempts = 3
    for attempt in range(attempts):
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode())
            content = data["choices"][0]["message"]["content"]
            if not content or not content.strip():
                # Reasoning models (e.g. glm-5.3-flash) can burn the entire
                # max_tokens budget on thinking tokens and return content=null.
                raise RuntimeError(
                    "model returned empty content — likely reasoning consumed "
                    "the max_tokens budget; raise AI_REVIEW_MAX_TOKENS "
                    "(default 4000; try 16000 for reasoning models)"
                )
            return content
        except urllib.error.HTTPError as e:
            body = ""
            with contextlib.suppress(Exception):
                body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                wait = 5 * (attempt + 1)
                print(
                    f"HTTP {e.code} from provider, retrying in {wait}s "
                    f"({attempt + 1}/{attempts})… {body}",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(f"provider HTTP {e.code}: {body}") from e


def main():
    token = os.environ["GITHUB_TOKEN"]
    api_key = os.environ["AI_REVIEW_API_KEY"]
    base_url = os.environ.get("AI_REVIEW_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_REVIEW_MODEL", "gpt-4o")
    max_tokens = int(os.environ.get("AI_REVIEW_MAX_TOKENS", "4000"))
    repo = os.environ["REPO"]
    number = int(os.environ["PR_NUMBER"])

    pr = gh(f"/repos/{repo}/pulls/{number}", token)
    sha = pr["head"]["sha"]
    title = pr["title"]
    body = (pr.get("body") or "")[:4000]
    diff = get_diff(repo, number, token)
    if len(diff) > 180_000:
        diff = diff[:180_000] + "\n\n… (diff truncated at 180KB)"
    changed = [f["filename"] for f in gh(f"/repos/{repo}/pulls/{number}/files?per_page=100", token)]

    system = open("prompts/reviewer.md").read()
    try:
        agents_md = open("AGENTS.md").read()[:12000]
    except FileNotFoundError:
        agents_md = "(AGENTS.md not found)"

    user = f"""Review this pull request.

## PR #{number}: {title}

### PR description (from author)
{body}

### Changed files ({len(changed)})
{chr(10).join(changed)}

### Repository intent layer (AGENTS.md excerpt)
{agents_md}

### Diff
```diff
{diff}
```
"""
    print(
        f"Reviewing PR #{number} ({len(changed)} files, {len(diff)} diff bytes) with {model}…",
        file=sys.stderr,
    )
    review = llm(system, user, base_url, api_key, model, max_tokens=max_tokens)

    marker = f"<!-- ai-review:sha={sha} -->"
    comment_body = f"{marker}\n{review}\n\n*(automated review by `{model}` — advisory only)*"

    if os.environ.get("AI_REVIEW_DRY_RUN") == "1":
        print("--- AI_REVIEW_DRY_RUN=1: review NOT posted ---\n", file=sys.stderr)
        print(comment_body)
        return

    # Idempotency: find existing ai-review comment by marker. Paginated —
    # a PR with >100 comments kept its marker off page 1 and every
    # synchronize re-posted the review.
    comments = []
    for page in range(1, 4):  # 300 comments covers every real PR
        batch = gh(f"/repos/{repo}/issues/{number}/comments?per_page=100&page={page}", token)
        comments.extend(batch)
        if len(batch) < 100:
            break
    existing = next((c for c in comments if "ai-review:sha=" in (c.get("body") or "")), None)
    if existing and marker in existing["body"]:
        print(f"Review for {sha[:8]} already posted — skipping.", file=sys.stderr)
        return
    # If an older ai-review comment exists (different sha), post a new one —
    # the per-SHA review history is the audit trail (each push gets its own
    # review; markers make them grep-able).
    gh(
        f"/repos/{repo}/issues/{number}/comments",
        token,
        method="POST",
        payload={"body": comment_body},
    )
    print("Review posted.", file=sys.stderr)


if __name__ == "__main__":
    main()
