import { describe, expect, it } from "vitest";
import { ACTIONS, createEmptySession, projectSessionReducer } from "./projectSession.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";

const CLASH = {
  level: "error",
  code: "i2c_address_clash",
  message: "2 devices on one I2C bus would all answer at 0x77: BME280 (n2), BME280 (n4). They cannot both work.",
};

function sessionFor(gate, gates = { compile_ok: false }) {
  return projectSessionReducer(createEmptySession(), {
    type: ACTIONS.HYDRATE_CURRENT_RESULT,
    jobId: "job_1",
    result: {
      build_dir: "/tmp/b",
      ok: false,
      design_quality_gate: gate,
      project_package: { build_dir: "/tmp/b", gates },
    },
  });
}

describe("deriveProjectTruth with an electrical error", () => {
  it("says there is an electrical problem and states it, instead of calling it a DRC error", () => {
    const truth = deriveProjectTruth(
      sessionFor({ build_ready: false, summary: { electrical_issues: [CLASH] } })
    );

    expect(truth.design.state).toBe("electrical_error");
    expect(truth.design.label).toBe("Electrical problem");
    expect(truth.design.label).not.toMatch(/DRC/);
    expect(truth.design.detail).toContain("0x77");
    expect(truth.overall.headline).toMatch(/electrical problem/i);
  });

  it("does not let a clean DRC hide an electrical error", () => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        design_quality: { kicad_drc_errors: 0 },
        design_quality_gate: { build_ready: false, summary: { electrical_issues: [CLASH] } },
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
      },
    });

    expect(deriveProjectTruth(session).design.state).toBe("electrical_error");
  });

  it("keeps a missing requested part as the first thing said", () => {
    const mismatch = { status: "mismatch", missing_parts: [{ module_id: "sg90", names: ["pan"], requested: 2, in_design: 1 }] };
    const truth = deriveProjectTruth(
      sessionFor({ build_ready: false, request_fidelity: mismatch, summary: { electrical_issues: [CLASH] } })
    );

    expect(truth.design.state).toBe("request_mismatch");
  });

  it("ignores warnings and notes, and leaves a clean design as it was", () => {
    const warn = { level: "warn", message: "needs a person to set the address" };
    const info = { level: "info", message: "confirm pull-ups" };
    const truth = deriveProjectTruth(
      sessionFor({ build_ready: true, summary: { electrical_issues: [warn, info] } }, { compile_ok: true })
    );

    expect(truth.design.state).toBe("drc_clean");
  });
});
