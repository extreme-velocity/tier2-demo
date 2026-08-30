#!/usr/bin/env python3
"""Repo velocity metrics — the analysis run against hermes-agent, packaged
for any repo. Uses only the GitHub REST API (no GraphQL needed).

Usage:
  GH_TOKEN=… python scripts/repo_metrics.py --repo owner/name [--days 90]
  --markdown   print a markdown report
  --post       post/refresh a comment on issue $DASHBOARD_ISSUE
  --json       dump raw metrics JSON

Metrics (the "AI-velocity" dashboard):
  Commits: per-day, top authors, concentration, conventional-commit %
  PRs: merge funnel, merge latency percentiles (the headline number),
       fork vs same-repo merge rates, formal-review coverage
  Issues: open/closed, median close latency
  AI-fleet: bot account activity (formal reviews + PRs by Bot authors)
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta

API = "https://api.github.com"


def gh(path, token):
    req = urllib.request.Request(
        f"{API}{path}", headers={"Authorization": f"Bearer {token}", "User-Agent": "metrics"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def paged(path, token, max_pages=40):
    out = []
    for page in range(1, max_pages + 1):
        data = gh(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}", token)
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
    return out


def pctile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return round(s[max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))], 1)


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("REPO", "owner/name"))
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        sys.exit("GH_TOKEN required")

    since = datetime.now(UTC) - timedelta(days=args.days)
    out = {"repo": args.repo, "window_days": args.days}

    # --- commits ---
    commits = paged(f"/repos/{args.repo}/commits?since={since.isoformat()}", token)
    authors = Counter(
        (c.get("author") or {}).get("login") or c["commit"]["author"]["name"] for c in commits
    )
    CONV = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|bump)", re.IGNORECASE
    )
    conv = sum(1 for c in commits if CONV.match(c["commit"]["message"].splitlines()[0]))
    out["commits"] = {
        "total": len(commits),
        "per_day": round(len(commits) / args.days, 1),
        "unique_authors": len(authors),
        "top5_pct": round(
            100 * sum(v for _, v in authors.most_common(5)) / max(len(commits), 1), 1
        ),
        "conventional_pct": round(100 * conv / max(len(commits), 1), 1),
        "top_authors": authors.most_common(10),
    }

    # --- PRs (closed = merged+unmerged in window) ---
    prs = paged(f"/repos/{args.repo}/pulls?state=all&sort=updated&direction=desc", token)
    prs = [p for p in prs if parse(p["created_at"]) >= since]
    merged = [p for p in prs if p.get("merged_at")]
    lats = [(parse(p["merged_at"]) - parse(p["created_at"])).total_seconds() / 60 for p in merged]
    fork = [p for p in prs if (p.get("head") or {}).get("repo", {}).get("full_name") != args.repo]
    fork_m = [p for p in fork if p.get("merged_at")]
    bots = [p for p in prs if (p.get("user") or {}).get("type") == "Bot"]
    out["prs"] = {
        "created": len(prs),
        "merged": len(merged),
        "merge_rate_pct": round(100 * len(merged) / max(len(prs), 1), 1),
        "merge_latency_min": {
            "p10": pctile(lats, 10),
            "median": pctile(lats, 50),
            "p90": pctile(lats, 90),
            "under_1h_pct": round(100 * sum(1 for x in lats if x < 60) / max(len(lats), 1), 1),
        },
        "fork_merge_rate_pct": round(100 * len(fork_m) / max(len(fork), 1), 1),
        "bot_prs": len(bots),
        "bot_accounts": dict(
            Counter((p.get("user") or {}).get("login", "ghost") for p in bots).most_common(5)
        ),
    }

    # --- issues ---
    issues = paged(f"/repos/{args.repo}/issues?state=all&sort=updated&direction=desc", token)
    issues = [i for i in issues if "pull_request" not in i and parse(i["created_at"]) >= since]
    closed = [i for i in issues if i["state"] == "closed" and i.get("closed_at")]
    ilats = [
        (parse(i["closed_at"]) - parse(i["created_at"])).total_seconds() / 3600 for i in closed
    ]
    out["issues"] = {
        "created": len(issues),
        "closed": len(closed),
        "median_close_hours": pctile(ilats, 50),
    }

    if args.json:
        print(json.dumps(out, indent=2))

    c, p = out["commits"], out["prs"]
    md = f"""## 📊 Velocity report — {args.repo} (last {args.days}d)

| Metric | Value | Hermes @ scale (reference) |
|---|---|---|
| Commits/day | **{c["per_day"]}** | 175 |
| Unique commit authors | {c["unique_authors"]} | 3,328 |
| Top-5 author concentration | {c["top5_pct"]}% | 45% |
| Conventional commits | {c["conventional_pct"]}% | 88% |
| PRs created / merged | {p["created"]} / {p["merged"]} ({p["merge_rate_pct"]}%) | 16.6% merged |
| **Median merge latency** | **{p["merge_latency_min"]["median"]} min** | **21.8 min** |
| Merged < 1h | {p["merge_latency_min"]["under_1h_pct"]}% | 67% |
| Fork PR merge rate | {p["fork_merge_rate_pct"]}% | 3.8% |
| Bot PRs | {p["bot_prs"]} ({p["bot_accounts"]}) | 573 |
| Issues created / closed | {out["issues"]["created"]} / {out["issues"]["closed"]} | — |

Top authors: {", ".join(f"**{a}** ({v})" for a, v in c["top_authors"][:5])}
"""
    if args.markdown:
        print(md)

    if args.post:
        issue = os.environ.get("DASHBOARD_ISSUE")
        if not issue:
            print("DASHBOARD_ISSUE not set; printing only.")
            print(md)
            return
        marker = "<!-- velocity-report -->"
        # paginate the marker lookup — default page is 30 comments, after
        # which every weekly run would post a duplicate dashboard
        comments = []
        if token:
            for pg in range(1, 4):
                batch = gh(
                    f"/repos/{args.repo}/issues/{issue}/comments?per_page=100&page={pg}",
                    token,
                )
                comments.extend(batch)
                if len(batch) < 100:
                    break
        existing = next((cm for cm in comments if marker in (cm.get("body") or "")), None)
        payload = {"body": f"{marker}\n{md}"}
        req = urllib.request.Request(
            f"{API}/repos/{args.repo}/issues/{issue}/comments",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="PATCH" if existing else "POST",
        )
        if existing:
            req.full_url = f"{API}/repos/{args.repo}/issues/comments/{existing['id']}"
        else:
            req.full_url = f"{API}/repos/{args.repo}/issues/{issue}/comments"
        with urllib.request.urlopen(req):
            print("Posted." if not existing else "Updated.", file=sys.stderr)


if __name__ == "__main__":
    main()
