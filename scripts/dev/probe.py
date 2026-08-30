#!/usr/bin/env python3
"""Provider probe — one-shot connectivity test for the AI fleet.

Run this BEFORE wiring secrets into GitHub: it exercises the exact
request shape `ai_review.py` / `sweeper.py` use (OpenAI-compatible
chat completions, temperature + max_tokens) and reports latency,
token usage, and the two failure modes that bite reasoning models
(content=null from a blown thinking budget; hard 4xx from a bad key).

    python3 scripts/dev/probe.py \
        --base-url https://openrouter.ai/api/v1 \
        --model z-ai/glm-5.3-flash \
        --max-tokens 16000

    # against the local bridge (no key needed):
    python3 scripts/dev/probe.py --base-url http://127.0.0.1:8787/v1

Exit codes: 0 ok, 1 transport/HTTP error, 2 empty content (raise
--max-tokens).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def probe(base_url: str, model: str, api_key: str, max_tokens: int) -> int:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are terse. Reply with exactly: PROBE-OK"},
            {"role": "user", "content": "ping"},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        with contextlib_suppress():
            body = e.read().decode("utf-8", "replace")[:300]
        print(f"HTTP {e.code} from provider: {body}")
        return 1
    except Exception as e:
        print(f"transport error: {e}")
        return 1

    elapsed = time.monotonic() - started
    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    usage = data.get("usage") or {}
    finish = data["choices"][0].get("finish_reason")
    reasoning = bool(msg.get("reasoning") or msg.get("reasoning_content"))

    print(f"model      : {model}")
    print(f"latency    : {elapsed:.1f}s")
    print(f"finish     : {finish}")
    print(f"reasoning  : {'yes' if reasoning else 'no'}")
    tok = f"prompt={usage.get('prompt_tokens', '?')}"
    comp = f"completion={usage.get('completion_tokens', '?')}"
    print(f"tokens     : {tok} {comp}")

    if not content.strip():
        print(
            "content    : EMPTY — reasoning likely consumed the max_tokens "
            "budget; raise --max-tokens (16000 works for glm-5.3-flash on "
            "review-sized prompts)"
        )
        return 2
    print(f"content    : {content.strip()[:60]!r}")
    print("PROBE OK — provider is fleet-ready.")
    return 0


class contextlib_suppress:
    """Minimal context manager so this single-file probe has no imports
    beyond the standard urllib/json/argparse most readers expect."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    ap.add_argument("--model", default="z-ai/glm-5.3-flash")
    ap.add_argument("--api-key", default="local-dev")
    ap.add_argument("--max-tokens", type=int, default=4000)
    args = ap.parse_args()
    return probe(args.base_url, args.model, args.api_key, args.max_tokens)


if __name__ == "__main__":
    sys.exit(main())
