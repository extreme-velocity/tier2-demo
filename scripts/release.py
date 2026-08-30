#!/usr/bin/env python3
"""Release tool — conventional-commit changelog + semver + CalVer tag.

Flags:
  --part patch|minor|major   which semver part to bump (default: derived)
  --push                     push version commit
  --tag                      create + push the CalVer tag
  --gh-release               create the GitHub Release with the changelog

Contributor resolution: contributors/emails/<email> files map commit
authors → GitHub logins (salvage attribution). Unmapped non-noreply
emails are listed in the changelog as-is.

Dry-run by default — safe to execute locally.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path


def detect_repo_url():
    """Resolve the repo URL from the git remote — no placeholder to edit."""
    try:
        url = git("remote", "get-url", "origin")
    except Exception:
        return "https://github.com/OWNER/REPO"
    # Strip embedded credentials FIRST — a remote like
    # https://<token>@github.com/o/r.git must never leak into changelogs.
    if "@" in url and "://" in url:
        url = url.split("://", 1)[0] + "://" + url.rsplit("@", 1)[1]
    # ssh (git@github.com:o/r.git) or https (https://github.com/o/r.git)
    if url.startswith("git@"):
        return "https://github.com/" + url.split(":", 1)[1].removesuffix(".git")
    return url.removesuffix(".git")


VERSION_FILES = ["python/pyproject.toml", "typescript/package.json"]

CONV = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|bump)"
    r"(\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*(?P<desc>.+)",
    re.IGNORECASE,
)
CATEGORY_SECTIONS = [
    ("feat", "Features"),
    ("fix", "Bug Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("ci", "CI"),
    ("chore", "Chores"),
]


def git(*args, cwd=None):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True, cwd=cwd
    ).stdout.strip()


REPO_URL = detect_repo_url()


def load_contributor_dir(directory="contributors/emails"):
    mapping = {}
    d = Path(directory)
    if d.exists():
        for f in d.iterdir():
            if f.is_file():
                login = f.read_text().strip().splitlines()
                if login:
                    mapping[f.name] = login[0].strip()
    return mapping


AGENT_DOMAINS = (
    "users.noreply.github.com",
    "@github.com",
    "@anthropic.com",
    "@cursor.com",
    "@openai.com",
    "@aider.chat",
    "@copilot.com",
    "@gemini.google.com",
)


def resolve_author(name, email, contributor_map):
    if email in contributor_map:
        return contributor_map[email]
    m = re.match(r"(\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com", email)
    if m:
        return m.group("login")
    # AI-agent co-author identities resolve to nothing — an "@S" in the
    # credits is noise (keep the attribution where it belongs: trailers).
    if any(email.endswith(d) for d in AGENT_DOMAINS):
        return None
    return name or email


def get_commits(since_tag=None):
    rng = f"{since_tag}..HEAD" if since_tag else "HEAD~200..HEAD"
    try:
        raw = git("log", rng, "--format=%H%x1f%s%x1f%b%x1e")
    except subprocess.CalledProcessError:
        # shallow history / range too deep: take everything
        raw = git("log", "--format=%H%x1f%s%x1f%b%x1e")
    commits = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) < 3:
            parts += [""] * (3 - len(parts))
        h, subject, body = parts[0], parts[1], parts[2]
        an = git("log", "-1", h, "--format=%an")
        ae = git("log", "-1", h, "--format=%ae")
        commits.append(
            {"hash": h, "subject": subject, "body": body, "author_name": an, "author_email": ae}
        )
    return commits


def get_last_tag():
    tags = git("tag", "--sort=-creatordate").splitlines()
    return tags[0] if tags else None


def get_current_version():
    py = Path("python/pyproject.toml")
    if py.exists():
        m = re.search(r'^version\s*=\s*"([^"]+)"', py.read_text(), re.MULTILINE)
        if m:
            return m.group(1)
    return "0.1.0"


def bump_version(current, part):
    major, minor, patch = (int(x) for x in current.split(".")[:3])
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def update_version_files(new_version):
    py = Path("python/pyproject.toml")
    if py.exists():
        py.write_text(
            re.sub(
                r'^version\s*=\s*"[^"]+"',
                f'version = "{new_version}"',
                py.read_text(),
                count=1,
                flags=re.MULTILINE,
            )
        )
    ts = Path("typescript/package.json")
    if ts.exists():
        ts.write_text(
            re.sub(r'"version":\s*"[^"]+"', f'"version": "{new_version}"', ts.read_text(), count=1)
        )
    for f in VERSION_FILES:
        p = Path(f)
        if p.exists():
            git("add", str(p))


def get_pr_number(subject):
    m = re.search(r"\(#(\d+)\)\s*$", subject)
    return m.group(1) if m else None


def parse_coauthors(body):
    """Human co-authors only. Agent identities (Claude/Cursor/Copilot/… or
    agent email domains) are skipped — their attribution lives in the
    trailer itself, and a broken mention like "@S" (the lazy-regex bug that
    truncated "Super Z") is worse than none."""
    out = []
    for m in re.finditer(r"Co-Authored-By:\s*([^<\n]+)\s*(?:<([^>]*)>)?", body, re.IGNORECASE):
        name, email = m.group(1).strip(), (m.group(2) or "").strip().lower()
        if not name:
            continue
        if email and any(email.endswith(d) for d in AGENT_DOMAINS):
            continue
        if re.match(r"^(claude|copilot|codex|cursor|aider|gemini|super z)\b", name, re.IGNORECASE):
            continue
        # GitHub logins contain no spaces — a spaced name is a display name
        # we cannot mention; skip rather than post a broken mention.
        if " " in name:
            continue
        out.append(name)
    return out


def generate_changelog(commits, semver, contributor_map):
    today = datetime.date.today().isoformat()
    lines = [f"## v{semver} ({today})", ""]

    def pr(c):
        n = get_pr_number(c["subject"])
        return f" ([#{n}]({REPO_URL}/pull/{n}))" if n else ""

    def author_link(c):
        login = resolve_author(c["author_name"], c["author_email"], contributor_map)
        # agent identities resolve to None — no broken "[@None]" mention
        return f" by [@{login}]" if login else ""

    for cat, title in CATEGORY_SECTIONS:

        def matches_cat(c, cat=cat):
            m = CONV.match(c["subject"])
            return bool(m and m.group(1).lower() == cat)

        entries = [c for c in commits if matches_cat(c)]
        if not entries:
            continue
        lines.append(f"### {title}")
        for c in entries:
            m = CONV.match(c["subject"])
            desc = m.group("desc").strip()
            scope = m.group("scope")
            prefix = f"**{scope}:** " if scope else ""
            coauth = "".join(f" & @{a}" for a in parse_coauthors(c["body"]))
            lines.append(f"- {prefix}{desc}{pr(c)}{author_link(c)}{coauth}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["patch", "minor", "major"], default=None)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--tag", action="store_true")
    ap.add_argument("--gh-release", action="store_true")
    args = ap.parse_args()
    if args.gh_release and not args.tag:
        ap.error("--gh-release requires --tag (the release must point at a tag)")

    contributor_map = load_contributor_dir()
    last_tag = get_last_tag()
    commits = get_commits(last_tag)
    current = get_current_version()

    # derive part if not given: breaking/feat → minor (0.x), else patch
    part = args.part
    if not part:

        def is_feat(c):
            m = CONV.match(c["subject"])
            return bool(m and m.group(1).lower() == "feat")

        has_feat = any(is_feat(c) for c in commits)
        part = "minor" if has_feat else "patch"

    new_version = bump_version(current, part)
    d = datetime.date.today()
    calver = f"v{d:%Y.%-m.%-d}" if sys.platform != "win32" else f"v{d:%Y.%m.%d}"

    changelog = generate_changelog(commits, new_version, contributor_map)

    # Dry-run by default: nothing is written unless --push is given (the
    # docstring always promised this; the code used to write version files
    # and CHANGELOG.md unconditionally).
    if args.push:
        if not Path("CHANGELOG.md").exists():
            Path("CHANGELOG.md").write_text("# Changelog\n\n")
        old = Path("CHANGELOG.md").read_text()
        Path("CHANGELOG.md").write_text(old.rstrip("\n") + "\n\n" + changelog + "\n")
        update_version_files(new_version)
        git("add", "CHANGELOG.md")
    else:
        print("(dry run — pass --push to write CHANGELOG.md + bump versions)\n")

    print(f"Version: {current} → {new_version} ({part})  |  tag: {calver}\n")
    print(changelog[:2000])

    if args.push:
        git("commit", "-m", f"chore(release): v{new_version}")
        # actions/checkout leaves a DETACHED HEAD; `git push origin HEAD`
        # fails with "destination is not a full refname". Resolve the target
        # branch explicitly (env first — GitHub provides GITHUB_REF_NAME).
        branch = os.environ.get("GITHUB_REF_NAME") or git("rev-parse", "--abbrev-ref", "HEAD")
        git("push", "origin", f"HEAD:refs/heads/{branch}")
    if args.tag:
        # Same-day second release: v2026.8.31 taken → v2026.8.31.2 (a plain
        # re-tag fails rc=128 and the release POST would 422 anyway).
        tag_name = calver
        n = 2
        while (
            subprocess.run(
                ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag_name}"],
                capture_output=True,
            ).returncode
            == 0
        ):
            tag_name = f"{calver}.{n}"
            n += 1
        git("tag", "-a", tag_name, "-m", f"v{new_version}")
        git("push", "origin", tag_name)
    if args.gh_release:
        import json
        import urllib.request

        token = os.environ.get("GH_TOKEN")
        body = {"tag_name": tag_name, "name": f"v{new_version} ({tag_name})", "body": changelog}
        m = re.search(r"github\.com/([^/]+/[^/]+)$", REPO_URL)
        api_repo = m.group(1) if m else REPO_URL
        req = urllib.request.Request(
            f"https://api.github.com/repos/{api_repo}/releases",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            print("Release created:", json.loads(r.read().decode())["html_url"])


if __name__ == "__main__":
    main()
