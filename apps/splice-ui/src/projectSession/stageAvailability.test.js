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
  designReady,
  nextStageAction,
  packageReady,
  stageIsAvailable,
  stageIsComplete,
  verifyReady,
} from "./stageAvailability.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";
import { derivePackageHandoff } from "./packageHandoff.js";

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
    const pkgAction = nextStageAction({ ...session, currentStage: STAGES.package });
    expect(pkgAction.enabled).toBe(true);
    expect(pkgAction.handoff.kind).toBe("job_bundle");
  });
});

describe("derivePackageHandoff", () => {
  it("uses build_package for synchronous Studio compile without job id", () => {
    const session = projectSessionReducer(
      createEmptySession({
        intakeComplete: true,
        projectId: "p1",
      }),
      {
        type: ACTIONS.APPLY_STUDIO_COMPILE,
        composeResult: { out_dir: "/tmp/studio_sync", phrase: "sync board" },
        drc: { outDir: "/tmp/studio_sync" },
        projectPackage: { build_dir: "/tmp/studio_sync", info: { project_name: "sync board" } },
        benchSession: { open_gate_count: 1 },
        buildDir: "/tmp/studio_sync",
      },
    );
    expect(session.activeJobId).toBeNull();
    const handoff = derivePackageHandoff(session);
    expect(handoff.kind).toBe("build_package");
    expect(handoff.available).toBe(true);
    expect(handoff.url).toContain("/v1/build-files/package-archive");
    expect(handoff.url).toContain(encodeURIComponent("/tmp/studio_sync"));
  });

  it("uses job_bundle when an async job id is present", () => {
    const handoff = derivePackageHandoff(
      createEmptySession({
        activeJobId: "job_async",
        buildDir: "/tmp/async",
        projectPackage: { build_dir: "/tmp/async" },
        packageHandoff: null,
      }),
    );
    expect(handoff.kind).toBe("job_bundle");
    expect(handoff.url).toContain("/v1/jobs/job_async/bundle");
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
    expect(truth.bench.state).toBe("authorization_pending");
    expect(truth.bench.label).toMatch(/authorization pending|needs review/i);
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

  it("does not treat simulated:false alone as physical evidence", () => {
    const fromBench = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0 },
        projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true } },
        benchSession: {
          open_gate_count: 0,
          power_on_authorized: true,
          simulated: false,
        },
      }),
    );
    expect(fromBench.bench.physical).toBe(false);
    expect(fromBench.bench.state).not.toBe("physical_authorized");
    expect(fromBench.bench.state).toBe("authorization_pending");

    const fromGates = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0 },
        projectPackage: {
          build_dir: "/tmp/b",
          gates: { compile_ok: true, simulated: false, power_on_authorized: true, open_gate_count: 0 },
        },
      }),
    );
    expect(fromGates.bench.physical).toBe(false);
    expect(fromGates.bench.state).not.toBe("physical_authorized");
  });

  it("requires affirmative physical provenance for physical_authorized", () => {
    const phys = deriveProjectTruth(
      createEmptySession({
        intakeComplete: true,
        buildDir: "/tmp/b",
        designQuality: { kicad_drc_errors: 0, copper_tier: "review_required" },
        projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true } },
        benchSession: {
          open_gate_count: 0,
          power_on_authorized: true,
          evidence_kind: "physical",
          operator_id: "cafe_op_01",
        },
      }),
    );
    expect(phys.bench.state).toBe("physical_authorized");
    expect(phys.overall.state).toBe("authorized");
  });

  it("keeps simulated authorization as simulated_pass", () => {
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

  it("does not complete Bench for zero-gate authorization_pending", () => {
    const session = createEmptySession({
      intakeComplete: true,
      buildDir: "/tmp/b",
      projectPackage: { build_dir: "/tmp/b", gates: { compile_ok: true, open_gate_count: 0 } },
      benchSession: { open_gate_count: 0, power_on_authorized: false },
    });
    expect(deriveProjectTruth(session).bench.state).toBe("authorization_pending");
    expect(stageIsComplete(session, STAGES.bench)).toBe(false);
  });
});
