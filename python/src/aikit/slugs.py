"""Slug helpers for branch-name generation (used by the metrics dashboard).

Pure functions — trivially testable, no I/O.
"""

import unicodedata

_FALLBACK = "item"  # non-empty input must always yield a usable slug


def slugify(text: str, max_length: int = 64) -> str:
    """Convert text to a lowercase kebab-case ASCII slug.

    Invariants (tested in tests/test_slugs.py):
    - output matches [a-z0-9]+(-[a-z0-9]+)* — ASCII only, no leading /
      trailing '-', no '--'
    - non-empty for non-empty input (unknown glyphs fall back to
      `item`, e.g. slugify('!!!') == 'item')
    - at most max_length characters
    - idempotent: slugify(slugify(x)) == slugify(x)

    Unicode input is NFKD-normalized first, so accented and fullwidth
    forms fold to their ASCII equivalents ('cafe' with an accent ->
    'cafe'; fullwidth digits -> ASCII digits).
    """
    if max_length <= 0:
        raise ValueError("max_length must be positive")

    norm = unicodedata.normalize("NFKD", text.lower())
    out: list[str] = []
    for ch in norm:
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    slug = "".join(out).strip("-")

    if len(slug) > max_length:
        slug = slug[:max_length].strip("-")
    # Fallback respects max_length too ('!!!' with max_length=2 -> 'it'):
    # 'item' is dash-free, so slicing can never strand a separator.
    return (slug or _FALLBACK)[:max_length]
