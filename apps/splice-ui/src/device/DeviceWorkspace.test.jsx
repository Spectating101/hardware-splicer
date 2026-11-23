// @vitest-environment node
import { describe, expect, it } from "vitest";
import { withComparison } from "./DeviceWorkspace.jsx";

describe("comparison override", () => {
  const manifest = { compare: { base: "7", target: "5" }, revisions: [{ id: "7" }, { id: "5" }, { id: "5c" }] };

  it("compares two of the manifest's own revisions", () => {
    expect(withComparison(manifest, "?compare=5,5c").compare).toEqual({ base: "5", target: "5c" });
  });

  it("ignores unknown, repeated or malformed pairs", () => {
    for (const search of ["", "?compare=5,9", "?compare=5,5", "?compare=5", "?compare=7,5,5c"]) {
      expect(withComparison(manifest, search)).toBe(manifest);
    }
  });
});
