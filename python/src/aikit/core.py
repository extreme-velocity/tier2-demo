"""Example module — replace with your code.

Demonstrates the testing rules from AGENTS.md:
- Behavior contracts over snapshots (assert relationships, not literals)
- Pure functions where possible (trivially testable, no I/O)
"""


def merge_configs(base: dict, override: dict) -> dict:
    """Deep-merge override into base and return a NEW dict.

    Invariant (testable): the result contains every key from `base` and
    every key from `override`; override wins on conflict; inputs are
    never mutated.
    """
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge_configs(out[k], v)
        else:
            out[k] = v
    return out
