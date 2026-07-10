import { describe, expect, it } from "vitest";
import {
  STAGES,
  createEmptySession,
  projectSessionReducer,
  ACTIONS,
} from "./projectSession.js";
import {
  benchReady,
  buildStageTabs,
  copperHonestyLabel,
  designReady,
  evidenceLabel,
  nextStageAction,
  packageReady,
  stageIsAvailable,
  verifyReady,
} from "./stageAvailability.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";

describe("stageAvailability", () => {
  it("blocks Design until greenfield Intake completion", () => {
    const session = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    expect(designReady(session)).toBe(false);
    expect(verifyReady(session)).toBe(false);
    expect(benchReady(session)).toBe(false);
    expect(packageReady(session)).toBe(false);
    const tabs = buildStageTabs(session);
    expect(tabs.find((t) => t.id === STAGES.design).available).toBe(false);
    expect(tabs.find((t) => t.id === STAGES.verify).available).toBe(false);
    expect(tabs.find((t) => t.id === STAGES.package).available).toBe(false);
  });

  it("unlocks Design after COMMIT_INTAKE", () => {
    let session = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    session = projectSessionReducer(session, {
      type: ACTIONS.COMMIT_INTAKE,
      intake: { goal: "demo board", project_name: "demo" },
      goal: "demo board",
    });
    expect(designReady(session)).toBe(true);
    expect(session.currentStage).toBe(STAGES.design);
    expect(verifyReady(session)).toBe(false);
  });

  it("unlocks Verify after build hydration and Package after package exists", () => {
    let session = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    session = projectSessionReducer(session, {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_1",
      result: {
        build_dir: "/tmp/b",
        project_package: { build_dir: "/tmp/b", info: { project_name: "demo" } },
        design_quality: { kicad_drc_errors: 0, copper_tier: "cosmetic_preview" },
      },
    });
    expect(verifyReady(session)).toBe(true);
    expect(benchReady(session)).toBe(true);
    expect(packageReady(session)).toBe(true);
    expect(stageIsAvailable(session, STAGES.verify)).toBe(true);
    expect(nextStageAction({ ...session, currentStage: STAGES.verify }).label).toMatch(/bench/i);
  });

  it("labels preview copper and simulated evidence honestly", () => {
    const copper = copperHonestyLabel("cosmetic_preview");
    expect(copper.tone).toBe("warn");
    expect(copper.title).toMatch(/preview/i);
    const sim = evidenceLabel({ simulated: true, open_gate_count: 0 }, null);
    expect(sim.label).toMatch(/Simulated/i);
  });
});

describe("deriveProjectTruth", () => {
  it("distinguishes DRC clean + preview copper", () => {
    const truth = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0, copper_tier: "cosmetic_preview" },
        projectPackage: {
          build_dir: "/tmp/b",
          gates: { compile_ok: true, copper_tier: "cosmetic_preview", open_gate_count: 0 },
        },
        benchSession: { open_gate_count: 0, power_on_authorized: false },
      }),
    );
    expect(truth.design.state).toBe("drc_clean");
    expect(truth.copper.state).toBe("preview_only");
    expect(truth.overall.headline).toMatch(/Copper preview only|Not fabrication-ready|bench/i);
  });

  it("distinguishes DRC clean + bench gates open", () => {
    const truth = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0, copper_tier: "cosmetic_preview" },
        projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true } },
        benchSession: { open_gate_count: 3, critical_open_count: 1, power_on_authorized: false },
      }),
    );
    expect(truth.design.state).toBe("drc_clean");
    expect(truth.bench.state).toBe("gates_open");
    expect(truth.overall.state).toBe("power_on_blocked");
  });

  it("keeps simulated pass separate from physical authorization", () => {
    const sim = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0 },
        projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true } },
        benchSession: {
          open_gate_count: 0,
          power_on_authorized: true,
          simulated: true,
          evidence_kind: "simulated",
        },
      }),
    );
    expect(sim.bench.state).toBe("simulated_pass");
    expect(sim.overall.state).toBe("review_required");

    const phys = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0, copper_tier: "review_required" },
        projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true } },
        benchSession: {
          open_gate_count: 0,
          power_on_authorized: true,
          simulated: false,
          evidence_kind: "physical",
        },
      }),
    );
    expect(phys.bench.state).toBe("physical_authorized");
    expect(phys.overall.state).toBe("authorized");
  });

  it("does not treat missing compile_ok as DRC/compile success", () => {
    const truth = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        projectPackage: { build_dir: "/tmp/b", gates: {} },
        designQuality: {},
      }),
    );
    expect(truth.design.state).toBe("unknown");
    expect(truth.design.state).not.toBe("drc_clean");
  });
});
