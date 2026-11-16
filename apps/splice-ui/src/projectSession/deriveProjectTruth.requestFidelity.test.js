import { describe, expect, it } from "vitest";
import { ACTIONS, createEmptySession, projectSessionReducer } from "./projectSession.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";

const MISMATCH = {
  status: "mismatch",
  missing_parts: [
    { module_id: "sg90", names: ["SG90 pan servo", "SG90 tilt servo"], requested: 2, in_design: 1 },
  ],
};

function sessionFor(result) {
  return projectSessionReducer(createEmptySession(), {
    type: ACTIONS.HYDRATE_CURRENT_RESULT,
    jobId: "job_1",
    result: { build_dir: "/tmp/b", ...result },
  });
}

describe("deriveProjectTruth with a request comparison", () => {
  it("names the missing part instead of calling a failed build a DRC error", () => {
    const session = sessionFor({
      ok: false,
      design_quality_gate: { build_ready: false, request_fidelity: MISMATCH },
      project_package: { build_dir: "/tmp/b", gates: { compile_ok: false } },
    });

    const truth = deriveProjectTruth(session);

    expect(truth.design.state).toBe("request_mismatch");
    expect(truth.design.label).toBe("Missing requested part");
    expect(truth.design.detail).toContain("sg90");
    expect(truth.design.detail).toContain("requested 2");
    expect(truth.design.label).not.toMatch(/DRC/);
  });

  it("does not let a clean DRC hide a missing requested part", () => {
    const session = sessionFor({
      design_quality: { kicad_drc_errors: 0 },
      design_quality_gate: { build_ready: false, request_fidelity: MISMATCH },
      project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
    });

    expect(deriveProjectTruth(session).design.state).toBe("request_mismatch");
  });

  it("leaves the existing states alone when the request matches", () => {
    const session = sessionFor({
      design_quality: { kicad_drc_errors: 0 },
      design_quality_gate: { build_ready: true, request_fidelity: { status: "matches", missing_parts: [] } },
      project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
    });

    expect(deriveProjectTruth(session).design.state).toBe("drc_clean");
  });

  it("tells the person what to do about it", () => {
    const session = sessionFor({
      design_quality_gate: { build_ready: false, request_fidelity: MISMATCH },
      project_package: { build_dir: "/tmp/b", gates: { compile_ok: false } },
    });

    expect(deriveProjectTruth(session).overall.headline).toMatch(/part you asked for/i);
  });
});
