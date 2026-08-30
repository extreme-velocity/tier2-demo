import { describe, expect, it } from "vitest";
import { mergeConfigs } from "../src/core.js";

describe("mergeConfigs", () => {
  it("contains every key from both inputs; override wins", () => {
    const result = mergeConfigs(
      { a: 1, nested: { x: 1, y: 2 } },
      { nested: { y: 99 }, b: 3 },
    );
    expect(Object.keys(result).sort()).toEqual(["a", "b", "nested"]);
    expect(result.nested).toEqual({ x: 1, y: 99 });
  });

  it("never mutates inputs", () => {
    const base = { nested: { x: 1 } };
    mergeConfigs(base, { nested: { x: 2 } });
    expect(base.nested.x).toBe(1);
  });
});
