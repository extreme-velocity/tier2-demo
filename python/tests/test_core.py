"""Tests assert INVARANTS (behavior contracts), not current values.

A change-detector test would be `assert merge_configs({}, {}) == {}`-style
snapshotting of complex outputs. Instead: assert the properties that must
hold for ANY correct implementation.
"""

from aikit.core import merge_configs


def test_merge_contains_all_keys_and_override_wins():
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    override = {"nested": {"y": 99}, "b": 3}
    result = merge_configs(base, override)

    # Invariant: every key from both inputs is present
    assert set(result) == {"a", "b", "nested"}
    # Invariant: override wins on conflict
    assert result["nested"]["y"] == 99
    # Invariant: non-conflicting keys survive
    assert result["nested"]["x"] == 1
    assert result["a"] == 1 and result["b"] == 3


def test_inputs_never_mutated():
    base = {"nested": {"x": 1}}
    override = {"nested": {"x": 2}}
    result = merge_configs(base, override)
    assert base["nested"]["x"] == 1  # input untouched
    assert result["nested"]["x"] == 2
    assert result["nested"] is not base["nested"]  # new object
