import { describe, expect, it } from "vitest";
import { describeTransition, invalidationReason } from "./checkTransition.js";

const r = (passed, actual, limit, unit = "h") => ({ passed, actual, limit, unit });

describe("describeTransition", () => {
  it("calls a failure caused only by a raised requirement a requirement change, not a regression", () => {
    expect(describeTransition(r(true, 3.166, 2.5), r(false, 3.166, 3.5), "regressed")).toEqual({
      kind: "newly-fails-requirement", label: "Newly fails: requirement increased",
      detail: "Measured 3.166 h, unchanged · target 3.5 h, up from 2.5 h",
    });
  });
  it("keeps 'regressed' for a worse measurement against the same limit", () => {
    expect(describeTransition(r(true, 240, 250, "g"), r(false, 264.9, 250, "g"), "regressed")).toMatchObject({
      kind: "regressed", detail: "Measured 264.9 g, was 240 g · target 250 g, unchanged",
    });
  });
  it("names both changes when the measurement and the limit moved", () => {
    expect(describeTransition(r(true, 3.2, 2.5), r(false, 3.0, 3.5)).label).toBe("Newly fails: measured value and requirement increased");
  });
  it("describes passes regained by a relaxed requirement and unchanged results", () => {
    expect(describeTransition(r(false, 3.1, 3.5), r(true, 3.1, 3)).label).toBe("Newly passes: requirement lowered");
    expect(describeTransition(r(true, .48, .3, "A"), r(true, .48, .3, "A"), "unchanged").label).toBe("Unchanged · passes in both");
  });
  it("falls back when a side is missing", () => {
    expect(describeTransition(null, r(true, 1, 0)).label).toBe("Not run in the earlier revision");
  });
});

describe("invalidationReason", () => {
  it("says a requirement changed", () => {
    expect(invalidationReason([{ kind: "changed_dependency", ids: ["requirement:minimum_work_runtime_h"] }])).toBe("changed requirement");
    expect(invalidationReason([])).toBe("reason not given");
  });
});
