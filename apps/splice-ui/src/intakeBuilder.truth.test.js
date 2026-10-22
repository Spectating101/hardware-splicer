import { describe, expect, it } from "vitest";
import { buildIntakeFromWizard, INITIAL_WIZARD } from "./intakeBuilder.js";

describe("donor intake evidence boundary", () => {
  it("does not assign a voltage or current to an unmeasured donor motor", () => {
    const intake = buildIntakeFromWizard({
      ...INITIAL_WIZARD,
      goal: "Repurpose an unknown toy motor for a small rover",
      mode: "salvage",
      parts: [{ name: "Recovered motor", type: "dc_motor", condition: "salvaged", notes: "" }],
    });
    expect(intake.available_parts).toHaveLength(1);
    expect(intake.available_parts[0]).toEqual({
      name: "Recovered motor",
      type: "dc_motor",
      condition: "salvaged",
    });
    expect(intake.available_parts[0]).not.toHaveProperty("voltage_v");
    expect(intake.available_parts[0]).not.toHaveProperty("current_a");
  });
});
