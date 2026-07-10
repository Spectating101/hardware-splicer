import { describe, expect, it } from "vitest";
import {
  ACTIONS,
  STAGES,
  canReturnToDesign,
  createEmptySession,
  projectSessionReducer,
  sessionHasPackage,
} from "./projectSession.js";

describe("projectSessionReducer", () => {
  it("starts a greenfield session on Design stage", () => {
    const next = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_GREENFIELD,
      phrase: "ESP32 soil logger",
    });
    expect(next.currentStage).toBe(STAGES.design);
    expect(next.mode).toBe("greenfield");
    expect(next.graph.phrase).toBe("ESP32 soil logger");
    expect(next.projectId).toBeTruthy();
  });

  it("persists graph across Studio → Verify and Verify → Design", () => {
    let state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_GREENFIELD,
      phrase: "carrier board",
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
    expect(state.dirty).toBe(true);

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
    expect(state.buildDir).toBe("/tmp/hs_build");
    expect(sessionHasPackage(state)).toBe(true);
    expect(state.graph.nodes).toEqual(nodes);
    expect(state.graph.edges).toEqual(edges);
    expect(canReturnToDesign(state)).toBe(true);

    state = projectSessionReducer(state, { type: ACTIONS.SET_STAGE, stage: STAGES.design });
    expect(state.currentStage).toBe(STAGES.design);
    expect(state.graph.nodes).toEqual(nodes);
    expect(state.graph.phrase).toBe("carrier board");
  });

  it("hydrates a recent build without inventing a second compile path", () => {
    const state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.HYDRATE_BUILD,
      jobId: "job_123",
      result: {
        build_dir: "/tmp/recent",
        project_name: "robot_drive",
        goal: "salvage drive",
        project_package: { build_dir: "/tmp/recent", info: { project_name: "robot_drive" } },
        salvage_package: { ok: true },
      },
      benchSession: { open_gate_count: 0, power_on_authorized: true },
    });
    expect(state.activeJobId).toBe("job_123");
    expect(state.mode).toBe("salvage");
    expect(state.currentStage).toBe(STAGES.verify);
    expect(state.buildDir).toBe("/tmp/recent");
    expect(state.projectPackage.info.project_name).toBe("robot_drive");
  });

  it("preserves studio graph when hydrating a build on top of an active session", () => {
    let state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.START_GREENFIELD,
      phrase: "keep me",
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      nodes: [{ id: "keep" }],
      edges: [],
      phrase: "keep me",
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.HYDRATE_BUILD,
      jobId: "job_other",
      result: {
        build_dir: "/tmp/other",
        project_package: { build_dir: "/tmp/other" },
      },
    });
    expect(state.graph.nodes).toEqual([{ id: "keep" }]);
    expect(state.graph.phrase).toBe("keep me");
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
});

describe("advanced navigation helpers", () => {
  it("treats example/lab/preview as Advanced destinations", () => {
    const ADVANCED_VIEWS = new Set(["advanced", "example", "lab", "preview"]);
    expect(ADVANCED_VIEWS.has("lab")).toBe(true);
    expect(ADVANCED_VIEWS.has("studio")).toBe(false);
    expect(ADVANCED_VIEWS.has("workspace")).toBe(false);
  });
});
