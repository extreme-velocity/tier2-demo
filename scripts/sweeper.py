#!/usr/bin/env python3
"""Triage sweeper runner — fetches stale items, runs the sweeper LLM,
applies verdicts (label / comment / close-within-limits).

Contract: prompts/sweeper.md. Guardrails:
  - max items per run, max closes per run (circuit breaker)
  - never closes maintainer-authored items (roster: contributors/maintainers.txt)
  - idempotent via <!-- sweeper:verdict=... --> marker comments
  - closes only at confidence=high with one of three allowed reasons

Close-authority gradient (the tier system's safety model):
  - SWEEPER_ALLOW_CLOSES=0 (default): the sweeper RECOMMENDS closes
    (marker verdict=recommend-close + `sweeper:recommend-close` label)
    but never executes one. Internal-tier posture.
  - SWEEPER_ALLOW_CLOSES=1: executes high-confidence closes within the
    three-reason policy. Public-OSS posture, after a label-only audit
    period.

SWEEPER_DRY_RUN=1 prints verdicts without touching GitHub (model testing).

Maintainer roster: contributors/maintainers.txt, one GitHub login per
line (# comments allowed). Without a roster the sweeper refuses to close —
safe by default. Override with SWEEPER_MAINTAINERS="a,b" if you don't
want the file.
"""

import contextlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://api.github.com"


def gh(path, token, method="GET", payload=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sweeper",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode()
        return json.loads(body) if body else {}


def llm(system, user, base_url, api_key, model, max_tokens=2000):
    """One chat completion with retry/backoff on 429 + 5xx (free tiers).

    The sweeper makes many small calls per run; transient provider 429s
    are routine on shared pools. Retry with backoff, bubble hard errors.
    """
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    attempts = 3
    for attempt in range(attempts):
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                content = json.loads(resp.read().decode())["choices"][0]["message"]["content"]
            if not content or not content.strip():
                # Reasoning models can burn the whole max_tokens budget on
                # thinking and return content=null — skip the item, don't
                # crash the run (ai_review.py fails fast; here one bad item
                # must not kill the sweep).
                print("model returned empty content — skipping item", file=sys.stderr)
                return None
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


def extract_verdict_json(raw):
    r"""Extract the verdict object from an LLM response.

    The old `re.search(r"\{.*\}")` greedy match grabbed the FIRST brace to
    the LAST brace — prose containing braces ("Option {A} … {json}") produced
    unparsable strings and the item was retried (and paid for) every run.
    Scan balanced top-level objects instead, parse each, return the LAST one
    that parses (models emit the verdict after their reasoning)."""
    if not raw:
        return None
    candidates = []
    depth, start = 0, None
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(raw[start : i + 1])
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def repo_tree():
    """File listing for the sweep prompt.

    e2e-discovered gap: without repo context the sweeper CANNOT honestly
    verify `implemented_on_main` — it either keeps everything open (safe
    but useless) or hallucinates a close (dangerous). The file tree gives
    the model real signal to correlate an item's request against what
    already exists on main."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        if out:
            files = out.splitlines()
            return "\n".join(files[:400]) + (
                f"\n… (+{len(files) - 400} more)" if len(files) > 400 else ""
            )
    except Exception:
        pass
    return "(file listing unavailable)"


def load_maintainers():
    """Maintainer logins: contributors/maintainers.txt (one per line, # =
    comment) or SWEEPER_MAINTAINERS="a,b". Empty set → sweeper cannot close."""
    path = Path("contributors/maintainers.txt")
    if path.exists():
        logins = {
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        if logins:
            return logins
    env = os.environ.get("SWEEPER_MAINTAINERS", "")
    return {m.strip() for m in env.split(",") if m.strip()}


def days_since(ts):
    if not ts:
        return 999
    return (datetime.now(UTC) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).days


def main():
    token = os.environ["GITHUB_TOKEN"]
    api_key = os.environ["AI_REVIEW_API_KEY"]
    base_url = os.environ.get("AI_REVIEW_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("AI_REVIEW_MODEL", "gpt-4o")
    repo = os.environ["REPO"]
    max_items = int(os.environ.get("MAX_ITEMS", "30"))
    max_closes = int(os.environ.get("SWEEPER_MAX_CLOSES", "10"))
    max_tokens = int(os.environ.get("SWEEPER_MAX_TOKENS", "4000"))

    system = open("prompts/sweeper.md").read()
    maintainers = load_maintainers()
    allow_closes = os.environ.get("SWEEPER_ALLOW_CLOSES", "0") == "1"
    if allow_closes and not maintainers:
        print(
            "WARNING: SWEEPER_ALLOW_CLOSES=1 but no maintainer roster found "
            "(contributors/maintainers.txt or SWEEPER_MAINTAINERS). "
            "Refusing to close — demoting to recommend-only.",
            file=sys.stderr,
        )
        allow_closes = False
    dry_run = os.environ.get("SWEEPER_DRY_RUN") == "1"
    closes_done = 0
    processed = 0
    tree = repo_tree()

    # Candidate queue: stale open PRs + issues (oldest-touched first)
    candidates = []
    for kind, path in (("pr", "pulls"), ("issue", "issues")):
        try:
            items = gh(
                f"/repos/{repo}/{path}?state=open&sort=updated&direction=asc&per_page=50", token
            )
        except Exception as e:
            print(f"fetch {path} failed: {e}", file=sys.stderr)
            continue
        for it in items:
            if kind == "issue" and "pull_request" in it:
                continue  # issues endpoint includes PRs
            candidates.append(
                {
                    "kind": kind,
                    "number": it["number"],
                    "title": it["title"],
                    "author": (it.get("user") or {}).get("login", ""),
                    "age_days": days_since(it["updated_at"]),
                    "body": (it.get("body") or "")[:3000],
                }
            )
    candidates.sort(key=lambda c: -c["age_days"])
    candidates = candidates[:max_items]
    print(f"{len(candidates)} candidates", file=sys.stderr)

    for c in candidates:
        if processed >= max_items:
            break
        # skip maintainer items
        if c["author"] in maintainers:
            continue
        # idempotency: check for existing marker (paginated — >100 comments
        # used to push the marker off page 1 and re-verdict every run)
        comments = []
        try:
            for page in range(1, 4):
                batch = gh(
                    f"/repos/{repo}/issues/{c['number']}/comments?per_page=100&page={page}",
                    token,
                )
                comments.extend(batch)
                if len(batch) < 100:
                    break
        except Exception:
            comments = []
        if any("sweeper:verdict=" in (x.get("body") or "") for x in comments):
            print(f"#{c['number']}: marker exists, skipping", file=sys.stderr)
            continue

        processed += 1
        user = f"""Sweep this item (kind={c["kind"]}, age since last update: {c["age_days"]} days):

#{c["number"]}: {c["title"]}
Author: {c["author"]}
Body:
{c["body"]}

Repository file listing on current main (use it to check whether the
request is already implemented — cite the exact path when it is):
{tree}

Respond with the JSON verdict object only."""
        try:
            raw = llm(system, user, base_url, api_key, model, max_tokens=max_tokens)
        except Exception as e:
            print(f"#{c['number']}: LLM error {e}", file=sys.stderr)
            time.sleep(2)
            continue
        if raw is None:
            time.sleep(1)
            continue
        v = extract_verdict_json(raw)
        if v is None:
            print(f"#{c['number']}: no parsable JSON verdict", file=sys.stderr)
            continue
        v.setdefault("item", c["number"])
        v.setdefault("verdict", "label-only")

        if dry_run:
            print(
                f"#{c['number']} [{c['kind']}] DRY-RUN verdict: {json.dumps(v, indent=2)}",
                file=sys.stderr,
            )
            time.sleep(1)
            continue

        # --- apply verdict ---
        wants_close = (
            v.get("verdict") == "close"
            and v.get("confidence") == "high"
            and v.get("close_reason") in ("implemented_on_main", "cannot_reproduce", "incoherent")
        )
        # The close-authority gradient: a close verdict the runner may not
        # execute becomes a recommendation for a human. Agents prepare
        # decisions; humans make them.
        close = wants_close and allow_closes and closes_done < max_closes

        # 1) Attempt the CLOSE first — before labels, before the marker.
        #    If the close fails we demote to recommend-close and the marker
        #    (built after) records what ACTUALLY happened; a verdict=close
        #    marker on an open item would be a false audit trail AND would
        #    block re-sweeping via the idempotency check.
        close_failed = False
        if close:
            state_payload = {
                "state": "closed",
                "state_reason": "completed"
                if v.get("close_reason") == "implemented_on_main"
                else "not_planned",
            }
            try:
                gh(
                    f"/repos/{repo}/issues/{c['number']}",
                    token,
                    method="PATCH",
                    payload=state_payload,
                )
                closes_done += 1
                print(f"#{c['number']}: CLOSED ({v.get('close_reason')})", file=sys.stderr)
            except Exception as e:
                print(f"#{c['number']}: close failed {e}", file=sys.stderr)
                close = False
                close_failed = True
        verdict_word = "close" if close else "recommend-close" if wants_close else v.get("verdict")

        # 2) Labels (recommend-close rides the same POST — appending after
        #    would silently drop it).
        labels = v.get("labels") or []
        if isinstance(labels, str):
            labels = [x.strip() for x in labels.split(",") if x.strip()]
        labels = [re.sub(r"\s+", "-", str(lbl))[:50] for lbl in labels if str(lbl).strip()]
        risk = v.get("risk")
        if not isinstance(risk, dict):
            risk = {}  # LLM schema drift must not kill the run
        if risk.get("blast_radius"):
            labels.append(f"sweeper:blast-{risk['blast_radius']}")
        for t in risk.get("touches") or []:
            if t and t != "none":
                labels.append(f"sweeper:risk-{t}")
        if wants_close and not close and not dry_run:
            labels.append("sweeper:recommend-close")
        if labels:
            try:
                gh(
                    f"/repos/{repo}/issues/{c['number']}/labels",
                    token,
                    method="POST",
                    payload={"labels": labels},
                )
            except Exception as e:
                print(f"#{c['number']}: label failed {e}", file=sys.stderr)

        # 3) Marker + comment — built AFTER the close attempt so they record
        #    the actual outcome.
        marker = (
            f"<!-- sweeper:item={c['number']} -->\n"
            f"<!-- sweeper:verdict={verdict_word} "
            f"reason={v.get('close_reason')} "
            f"confidence={v.get('confidence')} -->"
        )
        comment = v.get("comment")
        default_note = "(sweeper pass — labels applied; see verdict marker)"
        recommendation_note = (
            "\n\n*Sweeper close recommendation (reason: "
            f"{v.get('close_reason')}, confidence: {v.get('confidence')}) — "
            "close authority is not enabled on this repo; a maintainer "
            "makes the final call.*"
        )
        body_text = f"{marker}\n{comment or default_note}"
        if wants_close and not close:
            body_text += recommendation_note
        if close_failed:
            body_text += "\n\n*(close attempt failed — a maintainer should apply this manually)*"
        try:
            gh(
                f"/repos/{repo}/issues/{c['number']}/comments",
                token,
                method="POST",
                payload={"body": body_text},
            )
        except Exception as e:
            print(f"#{c['number']}: comment failed {e}", file=sys.stderr)
            continue
        print(
            f"#{c['number']}: {verdict_word} conf={v.get('confidence')} labels={labels}",
            file=sys.stderr,
        )
        time.sleep(1)

    print(
        f"Swept {processed} items, closed {closes_done} "
        f"(close authority: {'ON' if allow_closes else 'off — recommend-only'})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
