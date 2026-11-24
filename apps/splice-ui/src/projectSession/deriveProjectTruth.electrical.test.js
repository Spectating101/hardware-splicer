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

  it("still lists the electrical error and its repairs beside a missing requested part", () => {
    const mismatch = { status: "mismatch", missing_parts: [{ module_id: "sg90", names: ["pan"], requested: 2, in_design: 1 }] };
    const clash = {
      ...CLASH,
      repairs: [{ summary: "Set it to 0x76.", requires_person: true, physical_steps: ["Set the pin."] }],
    };
    const truth = deriveProjectTruth(
      sessionFor({ build_ready: false, request_fidelity: mismatch, summary: { electrical_issues: [clash] } })
    );

    const messages = truth.design.problems.map((p) => p.message);
    expect(messages.some((m) => m.includes("requested part sg90"))).toBe(true);
    expect(messages).toContain(CLASH.message);
    expect(truth.design.problems.find((p) => p.message === CLASH.message).repairs[0].requiresPerson).toBe(true);
    expect(truth.design.detail).toContain("0x77");
  });

  it("leaves a design with only notes as clean", () => {
    const info = { level: "info", message: "confirm pull-ups" };
    const truth = deriveProjectTruth(
      sessionFor({ build_ready: true, summary: { electrical_issues: [info] } }, { compile_ok: true })
    );

    expect(truth.design.state).toBe("drc_clean");
    expect(truth.design.problems).toEqual([]);
  });
});

const STRAP = {
  level: "warn",
  code: "i2c_address_declared_strap",
  message: "BME280 (n4) is declared at 0x76, not its default 0x77. That only works if a person sets the address pin on the board.",
  requires_person: true,
};

describe("deriveProjectTruth when the DRC is clean but the quality gate says not build-ready", () => {
  const blocked = {
    build_ready: false,
    blockers: [
      "Electrical safety has 1 warning(s) \u2014 resolve before fabrication.",
      STRAP.message,
    ],
    summary: { electrical_issues: [STRAP] },
  };

  it("does not show green DRC clean, and says it needs a person", () => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        design_quality: { kicad_drc_errors: 0 },
        design_quality_gate: blocked,
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
      },
    });
    const truth = deriveProjectTruth(session);

    expect(truth.design.state).toBe("needs_attention");
    expect(truth.design.label).not.toMatch(/clean/i);
    expect(truth.design.problems.map((p) => p.message)).toContain(STRAP.message);
    expect(truth.design.problems.find((p) => p.message === STRAP.message).needsPerson).toBe(true);
    expect(truth.overall.state).toBe("needs_verification");
    expect(truth.overall.headline).toMatch(/needs you/i);
  });

  it.each([
    ["failing KiCad ERC", "KiCad ERC failed with 3 error(s)."],
    ["an uncovered goal", "Selected design does not cover the stated goal: no sensor."],
  ])("shows %s from the gate instead of DRC clean", (_name, blocker) => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        design_quality: { kicad_drc_errors: 0 },
        design_quality_gate: { build_ready: false, blockers: [blocker], summary: { electrical_issues: [] } },
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
      },
    });
    const truth = deriveProjectTruth(session);

    expect(truth.design.state).toBe("needs_attention");
    expect(truth.design.problems.map((p) => p.message)).toEqual([blocker]);
    expect(truth.overall.state).toBe("needs_verification");
  });

  it("stays clean when the gate says build-ready", () => {
    const session = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        design_quality: { kicad_drc_errors: 0 },
        design_quality_gate: { build_ready: true, blockers: [], summary: { electrical_issues: [] } },
        project_package: { build_dir: "/tmp/b", gates: { compile_ok: true } },
      },
    });

    expect(deriveProjectTruth(session).design.state).toBe("drc_clean");
  });
});
