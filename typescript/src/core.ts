/**
 * Example module — mirrors python/src/aikit/core.py.
 * Tests assert invariants, never current-value snapshots.
 */

export function mergeConfigs<T extends Record<string, unknown>>(
  base: T,
  override: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...base };
  for (const [k, v] of Object.entries(override)) {
    const existing = out[k];
    out[k] =
      v &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      existing &&
      typeof existing === "object" &&
      !Array.isArray(existing)
        ? mergeConfigs(
            existing as Record<string, unknown>,
            v as Record<string, unknown>,
          )
        : v;
  }
  return out;
}
