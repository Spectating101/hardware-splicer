import { describe, expect, it } from "vitest";
import {
  ACTIONS,
  STAGES,
  canReturnToDesign,
  createEmptySession,
  projectSessionReducer,
  sessionHasPackage,
} from "./projectSession.js";
import { designReady } from "./stageAvailability.js";

describe("projectSessionReducer", () => {
  it("START_PROJECT opens Intake with a new identity and Design locked", () => {
    const next = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_PROJECT,
    });
    expect(next.currentStage).toBe(STAGES.intake);
    expect(next.projectId).toBeTruthy();
    expect(next.intakeComplete).toBe(false);
    expect(next.graph.nodes).toEqual([]);
    expect(designReady(next)).toBe(false);
  });

  it("COMMIT_INTAKE unlocks Design with goal preserved and no engine fields", () => {
    let state = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    state = projectSessionReducer(state, {
      type: ACTIONS.COMMIT_INTAKE,
      intake: {
        goal: "ESP32 soil moisture logger",
        project_name: "soil_logger",
        mode: "greenfield",
        designStrategy: "llm",
      },
      goal: "ESP32 soil moisture logger",
      projectName: "soil_logger",
      composeMode: "ai",
    });
    expect(state.intakeComplete).toBe(true);
    expect(state.designEditable).toBe(true);
    expect(state.currentStage).toBe(STAGES.design);
    expect(state.goal).toBe("ESP32 soil moisture logger");
    expect(state.graph.phrase).toBe("ESP32 soil moisture logger");
    expect(state.graph.composeMode).toBe("ai");
    expect(state.buildDir).toBeNull();
    expect(state.composeResult).toBeNull();
    expect(designReady(state)).toBe(true);
  });

  it("persists graph across Studio → Verify and Verify → Design", () => {
    let state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_PROJECT,
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.COMMIT_INTAKE,
      intake: { goal: "carrier board", project_name: "carrier" },
      goal: "carrier board",
      composeMode: "canvas",
    });
    const nodes = [{ id: "n1", data: { moduleId: "esp32" } }];
    const edges = [{ id: "e1", source: "n1", target: "n2" }];
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      nodes,
      edges,
      phrase: "carrier board",
      composeMode: "canvas",
    });

    state = projectSessionReducer(state, {
      type: ACTIONS.APPLY_STUDIO_COMPILE,
      composeResult: {
        ok: true,
        out_dir: "/tmp/hs_build",
        phrase: "carrier board",
        design_quality: { copper_tier: "cosmetic_preview" },
        agent_loop: { resolved: true },
      },
      drc: { outDir: "/tmp/hs_build", resolved: true },
      projectPackage: { build_dir: "/tmp/hs_build", info: { project_name: "carrier board" } },
      benchSession: { open_gate_count: 2, power_on_authorized: false },
    });

    expect(state.currentStage).toBe(STAGES.verify);
    expect(state.activeJobId).toBeNull();
    expect(state.graph.nodes).toEqual(nodes);
    expect(canReturnToDesign(state)).toBe(true);

    state = projectSessionReducer(state, { type: ACTIONS.SET_STAGE, stage: STAGES.design });
    expect(state.graph.nodes).toEqual(nodes);
    expect(state.graph.phrase).toBe("carrier board");
  });

  it("APPLY_STUDIO_COMPILE clears a stale previous-job bundle link and sets build_package handoff", () => {
    let state = createEmptySession({
      projectId: "proj_a",
      activeJobId: "job_stale",
      intakeComplete: true,
      graph: {
        nodes: [{ id: "n1" }],
        edges: [],
        phrase: "studio",
        composeMode: "canvas",
      },
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.APPLY_STUDIO_COMPILE,
      composeResult: { out_dir: "/tmp/studio", phrase: "studio" },
      drc: { outDir: "/tmp/studio" },
      projectPackage: { build_dir: "/tmp/studio" },
      benchSession: { open_gate_count: 0 },
    });
    expect(state.activeJobId).toBeNull();
    expect(sessionHasPackage(state)).toBe(true);
    expect(state.packageHandoff.kind).toBe("build_package");
    expect(state.packageHandoff.available).toBe(true);
  });

  it("LOAD_RECENT_BUILD without Studio graph is not editable Design", () => {
    let state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_PROJECT,
    });
    const projectA = state.projectId;
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      nodes: [{ id: "keep_me_from_a" }],
      edges: [],
      phrase: "Project A graph",
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.SET_ACTIVE_JOB,
      jobId: "job_a",
    });

    state = projectSessionReducer(state, {
      type: ACTIONS.LOAD_RECENT_BUILD,
      jobId: "job_b",
      result: {
        build_dir: "/tmp/project_b",
        project_name: "robot_drive",
        goal: "salvage drive",
        project_package: { build_dir: "/tmp/project_b", info: { project_name: "robot_drive" } },
        salvage_package: { ok: true },
        compose_result: { from: "b" },
      },
      benchSession: { open_gate_count: 0, power_on_authorized: true },
    });

    expect(state.projectId).toBe("job_b");
    expect(state.projectId).not.toBe(projectA);
    expect(state.activeJobId).toBe("job_b");
    expect(state.mode).toBe("salvage");
    expect(state.graph.nodes).toEqual([]);
    expect(state.graph.phrase).toBe("salvage drive");
    expect(state.designEditable).toBe(false);
    expect(state.sessionOrigin).toBe("recent_build");
    expect(state.composeResult).toEqual({ from: "b" });
    expect(state.buildDir).toBe("/tmp/project_b");
  });

  it("LOAD_RECENT_BUILD with stored Studio graph restores Design", () => {
    const state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.LOAD_RECENT_BUILD,
      jobId: "job_studio",
      result: {
        build_dir: "/tmp/studio_b",
        project_name: "logger",
        goal: "logger goal",
        project_package: { build_dir: "/tmp/studio_b" },
        studio_graph: {
          nodes: [{ id: "n1", data: { moduleId: "esp32" } }],
          edges: [],
          phrase: "logger goal",
          composeMode: "canvas",
        },
      },
    });
    expect(state.designEditable).toBe(true);
    expect(state.graph.nodes).toHaveLength(1);
    expect(state.graph.phrase).toBe("logger goal");
    expect(designReady(state)).toBe(true);
  });

  it("HYDRATE_CURRENT_RESULT keeps the same project identity for the active job", () => {
    let state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_PROJECT,
    });
    const id = state.projectId;
    state = projectSessionReducer(state, {
      type: ACTIONS.START_FROM_INTAKE,
      intake: { goal: "logger", project_name: "logger", mode: "salvage", donor_context: {} },
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: "job_current",
      result: {
        build_dir: "/tmp/current",
        project_package: { build_dir: "/tmp/current", info: { project_name: "logger" } },
      },
    });
    expect(state.projectId).toBe(id);
    expect(state.activeJobId).toBe("job_current");
    expect(state.currentStage).toBe(STAGES.verify);
    expect(state.intakeComplete).toBe(true);
  });

  it("patches package gates from bench submit", () => {
    let state = createEmptySession({
      projectPackage: { gates: { open_gate_count: 3 }, info: {} },
      displayResult: { project_package: { gates: { open_gate_count: 3 } } },
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.PATCH_PACKAGE_GATES,
      benchSession: {
        open_gate_count: 0,
        critical_open_count: 0,
        power_on_authorized: true,
      },
    });
    expect(state.projectPackage.gates.open_gate_count).toBe(0);
    expect(state.projectPackage.gates.power_on_authorized).toBe(true);
  });

  it("SYNC_GRAPH is a no-op when Design is not editable", () => {
    let state = createEmptySession({
      designEditable: false,
      graph: emptyPhraseGraph("locked"),
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      nodes: [{ id: "fake" }],
      phrase: "should not apply",
    });
    expect(state.graph.nodes).toEqual([]);
    expect(state.graph.phrase).toBe("locked");
  });
});

function emptyPhraseGraph(phrase) {
  return { nodes: [], edges: [], phrase, composeMode: "canvas" };
}
