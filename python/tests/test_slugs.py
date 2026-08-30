"""Invariant/property tests for slugify — assert the CONTRACT, not literals.

The first version of this file asserted exact outputs that froze the
implementation's bugs (trailing '-', 'café' leaking through). The AI
reviewer flagged them as worse than change-detectors: they enshrined
contract violations as expected behavior. These tests assert the
docstring's invariants over a corpus instead.
"""

import re

import pytest

from aikit.slugs import slugify

SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

_FULLWIDTH_ONE = "\uff11"  # ambiguous on purpose: Unicode-folding payload

CORPUS = [
    "Hello, World!",
    "caf\u00e9",
    "na\u00efve--BEHAVIOR",
    "Release 1.2 \u2014 final",
    "Fix/branch: quick---fix!!",
    "x\u00b2",
    _FULLWIDTH_ONE,
    "A" * 100,
    "  spaces  everywhere  ",
]


def test_slug_contract_holds_over_corpus():
    for text in CORPUS:
        s = slugify(text)
        assert SLUG_RE.fullmatch(s), f"{text!r} -> {s!r}"
        assert len(s) <= 64
        assert slugify(s) == s  # idempotent


def test_unicode_folds_to_ascii():
    assert slugify("caf\u00e9") == "cafe"
    assert slugify(_FULLWIDTH_ONE) == "1"


def test_edges_never_leading_trailing_dash():
    assert slugify("--Hello,, World!!") == "hello-world"
    assert slugify("!!!") == "item"  # documented fallback
    assert slugify("   ") == "item"


def test_truncation_never_strands_a_dash():
    for n in range(1, 16):
        s = slugify("ab cd ef gh ij kl", max_length=n)
        assert len(s) <= n
        assert not s.endswith("-"), f"max_length={n} -> {s!r}"


def test_max_length_must_be_positive():
    with pytest.raises(ValueError):
        slugify("anything", max_length=0)


def test_fallback_respects_max_length():
    # Failing-first for the round-3 review finding: the 'item' fallback
    # must not exceed max_length (and stays idempotent at small caps).
    for n in range(1, 6):
        s = slugify("!!!", max_length=n)
        assert len(s) <= n
        assert slugify(s, max_length=n) == s
