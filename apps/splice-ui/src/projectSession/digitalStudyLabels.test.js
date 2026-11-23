import { describe, expect, it } from "vitest";
import { factText, fieldLabel, keyLabel } from "./digitalStudyLabels.js";

describe("readable labels", () => {
  it("maps known keys to words with units", () => {
    expect(factText("minimum_work_runtime_h", 3.5)).toBe("Minimum work runtime · 3.5 h");
    expect(factText("cad_kernel_available", false)).toBe("CAD kernel available · no");
    expect(fieldLabel("work_runtime")).toBe("Work runtime (h)");
  });
  it("falls back to the key's own words for unmapped keys", () => {
    expect(keyLabel("peak_current_a_est")).toEqual({ label: "Peak current a est", unit: undefined });
    expect(keyLabel("coolantFlowMm")).toEqual({ label: "Coolant flow", unit: "mm" });
    expect(factText("location", null)).toBe("Location · unknown");
  });
});
