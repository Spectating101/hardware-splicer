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

describe("stageAvailability", () => {
  it("blocks Verify/Bench/Package before a build", () => {
    const session = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    expect(designReady(session)).toBe(true);
    expect(verifyReady(session)).toBe(false);
    expect(benchReady(session)).toBe(false);
    expect(packageReady(session)).toBe(false);
    const tabs = buildStageTabs(session);
    expect(tabs.find((t) => t.id === STAGES.verify).available).toBe(false);
    expect(tabs.find((t) => t.id === STAGES.package).available).toBe(false);
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
