/** Shared project-session model for the unified workbench UI. */

export const STAGES = Object.freeze({
  intake: "intake",
  design: "design",
  verify: "verify",
  bench: "bench",
  package: "package",
});

export const STAGE_ORDER = [
  STAGES.intake,
  STAGES.design,
  STAGES.verify,
  STAGES.bench,
  STAGES.package,
];

export const STAGE_LABELS = Object.freeze({
  [STAGES.intake]: "Intake",
  [STAGES.design]: "Design",
  [STAGES.verify]: "Verify",
  [STAGES.bench]: "Bench",
  [STAGES.package]: "Package",
});

export function createEmptySession(overrides = {}) {
  return {
    projectId: overrides.projectId || null,
    projectName: overrides.projectName || "",
    goal: overrides.goal || "",
    mode: overrides.mode || "greenfield", // greenfield | salvage
    intake: overrides.intake || null,
    constraints: overrides.constraints || null,
    graph: {
      nodes: overrides.graph?.nodes || [],
      edges: overrides.graph?.edges || [],
      phrase: overrides.graph?.phrase || "",
      composeMode: overrides.graph?.composeMode || "canvas",
    },
    buildDir: overrides.buildDir || null,
    activeJobId: overrides.activeJobId || null,
    composeResult: overrides.composeResult || null,
    designQuality: overrides.designQuality || null,
    agentLoop: overrides.agentLoop || null,
    projectPackage: overrides.projectPackage || null,
    benchSession: overrides.benchSession || null,
    displayResult: overrides.displayResult || null,
    currentStage: overrides.currentStage || STAGES.intake,
    dirty: Boolean(overrides.dirty),
  };
}

export const ACTIONS = Object.freeze({
  RESET: "RESET",
  START_GREENFIELD: "START_GREENFIELD",
  START_FROM_INTAKE: "START_FROM_INTAKE",
  SET_STAGE: "SET_STAGE",
  SYNC_GRAPH: "SYNC_GRAPH",
  APPLY_STUDIO_COMPILE: "APPLY_STUDIO_COMPILE",
  HYDRATE_BUILD: "HYDRATE_BUILD",
  SET_BENCH_SESSION: "SET_BENCH_SESSION",
  SET_ACTIVE_JOB: "SET_ACTIVE_JOB",
  PATCH_PACKAGE_GATES: "PATCH_PACKAGE_GATES",
});

function newProjectId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `proj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function projectSessionReducer(state, action) {
  switch (action.type) {
    case ACTIONS.RESET:
      return createEmptySession();

    case ACTIONS.START_GREENFIELD: {
      const phrase = action.phrase || "";
      return createEmptySession({
        projectId: newProjectId(),
        projectName: action.projectName || phrase || "Untitled project",
        goal: phrase || action.goal || "",
        mode: "greenfield",
        currentStage: STAGES.design,
        graph: {
          nodes: [],
          edges: [],
          phrase,
          composeMode: action.composeMode || "canvas",
        },
        dirty: false,
      });
    }

    case ACTIONS.START_FROM_INTAKE: {
      const intake = action.intake || {};
      return createEmptySession({
        projectId: newProjectId(),
        projectName: intake.project_name || intake.projectName || "Untitled project",
        goal: intake.goal || "",
        mode: intake.mode === "salvage" || intake.donor_context ? "salvage" : "greenfield",
        intake,
        currentStage: STAGES.intake,
        dirty: true,
      });
    }

    case ACTIONS.SET_STAGE: {
      const stage = action.stage;
      if (!STAGE_ORDER.includes(stage)) return state;
      return { ...state, currentStage: stage };
    }

    case ACTIONS.SYNC_GRAPH: {
      const graph = {
        nodes: action.nodes ?? state.graph.nodes,
        edges: action.edges ?? state.graph.edges,
        phrase: action.phrase ?? state.graph.phrase,
        composeMode: action.composeMode ?? state.graph.composeMode,
      };
      return {
        ...state,
        graph,
        goal: graph.phrase || state.goal,
        projectName: state.projectName || graph.phrase || "Untitled project",
        dirty: true,
      };
    }

    case ACTIONS.APPLY_STUDIO_COMPILE: {
      const {
        composeResult,
        drc,
        projectPackage,
        benchSession,
        buildDir,
      } = action;
      const phrase =
        composeResult?.phrase ||
        composeResult?.goal ||
        composeResult?.project_name ||
        state.graph.phrase ||
        state.goal;
      const dir =
        buildDir ||
        drc?.outDir ||
        composeResult?.out_dir ||
        projectPackage?.build_dir ||
        state.buildDir;
      const displayResult = {
        build_dir: dir,
        project_name: phrase,
        goal: composeResult?.goal || phrase,
        project_package: projectPackage,
        design_quality: composeResult?.design_quality || drc?.truth || state.designQuality,
        agent_loop: composeResult?.agent_loop || state.agentLoop,
        bench_session: benchSession
          ? {
              readiness: benchSession.readiness,
              open_gate_count: benchSession.open_gate_count,
              critical_open_count: benchSession.critical_open_count,
              power_on_authorized: benchSession.power_on_authorized,
              level: benchSession.level,
              gates: benchSession.gates,
            }
          : state.displayResult?.bench_session,
      };
      return {
        ...state,
        projectId: state.projectId || newProjectId(),
        projectName: phrase || state.projectName,
        goal: phrase || state.goal,
        buildDir: dir,
        composeResult: composeResult || state.composeResult,
        designQuality: displayResult.design_quality,
        agentLoop: displayResult.agent_loop,
        projectPackage: projectPackage || state.projectPackage,
        benchSession: benchSession || state.benchSession,
        displayResult,
        currentStage: STAGES.verify,
        dirty: false,
        // graph intentionally preserved from prior SYNC_GRAPH
      };
    }

    case ACTIONS.HYDRATE_BUILD: {
      const result = action.result || {};
      const pkg = result.project_package || null;
      const dir = result.build_dir || pkg?.build_dir || null;
      const name =
        result.project_name ||
        pkg?.info?.project_name ||
        state.projectName ||
        "Loaded build";
      return {
        ...state,
        projectId: state.projectId || action.jobId || newProjectId(),
        projectName: name,
        goal: result.goal || pkg?.info?.goal || state.goal,
        mode: result.salvage_package || result.donor_context ? "salvage" : state.mode || "greenfield",
        buildDir: dir,
        activeJobId: action.jobId ?? state.activeJobId,
        composeResult: result.compose_result || result.compose || state.composeResult,
        designQuality: result.design_quality || state.designQuality,
        agentLoop: result.agent_loop || state.agentLoop,
        projectPackage: pkg,
        benchSession: action.benchSession || result.bench_session || state.benchSession,
        displayResult: result,
        currentStage: action.stage || STAGES.verify,
        dirty: false,
        // Keep existing graph if any (studio continuity); do not wipe on recent-build load
        graph: state.graph?.nodes?.length
          ? state.graph
          : {
              nodes: [],
              edges: [],
              phrase: result.goal || pkg?.info?.goal || "",
              composeMode: "canvas",
            },
      };
    }

    case ACTIONS.SET_BENCH_SESSION:
      return {
        ...state,
        benchSession: action.benchSession,
        displayResult: state.displayResult
          ? {
              ...state.displayResult,
              bench_session: action.benchSession,
            }
          : state.displayResult,
      };

    case ACTIONS.SET_ACTIVE_JOB:
      return { ...state, activeJobId: action.jobId };

    case ACTIONS.PATCH_PACKAGE_GATES: {
      const session = action.benchSession;
      if (!session || !state.projectPackage) {
        return { ...state, benchSession: session || state.benchSession };
      }
      const nextPkg = {
        ...state.projectPackage,
        gates: {
          ...(state.projectPackage.gates || {}),
          open_gate_count: session.open_gate_count,
          critical_open_count: session.critical_open_count,
          power_on_authorized: session.power_on_authorized,
        },
      };
      return {
        ...state,
        benchSession: session,
        projectPackage: nextPkg,
        displayResult: state.displayResult
          ? {
              ...state.displayResult,
              project_package: nextPkg,
              bench_session: session,
            }
          : state.displayResult,
      };
    }

    default:
      return state;
  }
}

/** Pure helpers used by UI + tests */
export function canReturnToDesign(session) {
  return Boolean(session?.graph?.nodes?.length || session?.graph?.phrase);
}

export function sessionHasPackage(session) {
  return Boolean(session?.projectPackage);
}

export function sessionHasBuild(session) {
  return Boolean(session?.buildDir || session?.projectPackage);
}
