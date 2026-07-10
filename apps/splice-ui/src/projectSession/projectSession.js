/** Shared project-session model for the unified workbench UI (in-memory only). */

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

export function emptyGraph(phrase = "", composeMode = "canvas") {
  return {
    nodes: [],
    edges: [],
    phrase: phrase || "",
    composeMode: composeMode || "canvas",
  };
}

export function createEmptySession(overrides = {}) {
  const o = overrides && typeof overrides === "object" ? overrides : {};
  return {
    projectId: o.projectId || null,
    projectName: o.projectName || "",
    goal: o.goal || "",
    mode: o.mode || "greenfield",
    intake: o.intake || null,
    constraints: o.constraints || null,
    graph: o.graph || emptyGraph(),
    buildDir: o.buildDir || null,
    activeJobId: o.activeJobId || null,
    composeResult: o.composeResult || null,
    designQuality: o.designQuality || null,
    agentLoop: o.agentLoop || null,
    projectPackage: o.projectPackage || null,
    benchSession: o.benchSession || null,
    displayResult: o.displayResult || null,
    currentStage: o.currentStage || STAGES.intake,
    dirty: Boolean(o.dirty),
    intakeComplete: Boolean(o.intakeComplete),
    designEditable: o.designEditable !== undefined ? Boolean(o.designEditable) : true,
    sessionOrigin: o.sessionOrigin || "new", // new | current_job | recent_build
  };
}

export const ACTIONS = Object.freeze({
  RESET: "RESET",
  START_PROJECT: "START_PROJECT",
  /** Greenfield Intake finished — hand off to Design Studio (no engine call). */
  COMMIT_INTAKE: "COMMIT_INTAKE",
  /** Salvage/demo engine submission transition. */
  START_FROM_INTAKE: "START_FROM_INTAKE",
  SET_STAGE: "SET_STAGE",
  SYNC_GRAPH: "SYNC_GRAPH",
  APPLY_STUDIO_COMPILE: "APPLY_STUDIO_COMPILE",
  HYDRATE_CURRENT_RESULT: "HYDRATE_CURRENT_RESULT",
  LOAD_RECENT_BUILD: "LOAD_RECENT_BUILD",
  SET_BENCH_SESSION: "SET_BENCH_SESSION",
  SET_ACTIVE_JOB: "SET_ACTIVE_JOB",
  PATCH_PACKAGE_GATES: "PATCH_PACKAGE_GATES",
});

export function newProjectId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `proj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function resultIdentity(result = {}, pkg = null) {
  return {
    name: result.project_name || pkg?.info?.project_name || "Loaded build",
    goal: result.goal || pkg?.info?.goal || "",
    mode:
      result.salvage_package || result.donor_context || result.mode === "salvage"
        ? "salvage"
        : "greenfield",
    dir: result.build_dir || pkg?.build_dir || null,
  };
}

function hasReconstructableGraph(graph) {
  return Boolean(graph?.nodes?.length);
}

export function projectSessionReducer(state, action) {
  switch (action.type) {
    case ACTIONS.RESET:
      return createEmptySession();

    case ACTIONS.START_PROJECT:
      return createEmptySession({
        projectId: newProjectId(),
        projectName: action.projectName || "New project",
        goal: "",
        mode: "greenfield",
        currentStage: STAGES.intake,
        dirty: false,
        intakeComplete: false,
        designEditable: true,
        sessionOrigin: "new",
      });

    case ACTIONS.COMMIT_INTAKE: {
      const intake = action.intake || {};
      const goal = intake.goal || action.goal || state.goal || "";
      const projectName =
        intake.project_name || intake.projectName || action.projectName || state.projectName || "Untitled project";
      const composeMode =
        action.composeMode ||
        (intake.designStrategy === "llm" || intake.design_strategy === "llm" ? "ai" : "canvas");
      return {
        ...state,
        projectId: state.projectId || newProjectId(),
        projectName,
        goal,
        mode: "greenfield",
        intake,
        constraints: action.constraints || intake.constraints || state.constraints,
        graph: {
          nodes: state.graph?.nodes || [],
          edges: state.graph?.edges || [],
          phrase: goal,
          composeMode,
        },
        intakeComplete: true,
        designEditable: true,
        sessionOrigin: "new",
        currentStage: STAGES.design,
        dirty: true,
      };
    }

    case ACTIONS.START_FROM_INTAKE: {
      const intake = action.intake || {};
      const salvage = intake.mode === "salvage" || Boolean(intake.donor_context);
      return {
        ...createEmptySession({
          projectId: state.projectId || newProjectId(),
          projectName:
            intake.project_name || intake.projectName || state.projectName || "Untitled project",
          goal: intake.goal || state.goal || "",
          mode: salvage ? "salvage" : "greenfield",
          intake,
          currentStage: STAGES.verify,
          dirty: true,
          graph: state.graph,
          intakeComplete: true,
          designEditable: salvage ? false : hasReconstructableGraph(state.graph),
          sessionOrigin: "current_job",
        }),
      };
    }

    case ACTIONS.SET_STAGE: {
      const stage = action.stage;
      if (!STAGE_ORDER.includes(stage)) return state;
      return { ...state, currentStage: stage };
    }

    case ACTIONS.SYNC_GRAPH: {
      if (state.designEditable === false) return state;
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
      const { composeResult, drc, projectPackage, benchSession, buildDir, jobId } = action;
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
        design_quality: composeResult?.design_quality || drc?.truth || null,
        agent_loop: composeResult?.agent_loop || null,
        bench_session: benchSession
          ? {
              readiness: benchSession.readiness,
              open_gate_count: benchSession.open_gate_count,
              critical_open_count: benchSession.critical_open_count,
              power_on_authorized: benchSession.power_on_authorized,
              level: benchSession.level,
              gates: benchSession.gates,
              simulated: benchSession.simulated,
              evidence_kind: benchSession.evidence_kind,
            }
          : null,
      };
      return {
        ...state,
        projectId: state.projectId || newProjectId(),
        projectName: phrase || state.projectName,
        goal: phrase || state.goal,
        buildDir: dir,
        activeJobId: jobId ?? null,
        composeResult: composeResult || null,
        designQuality: displayResult.design_quality,
        agentLoop: displayResult.agent_loop,
        projectPackage: projectPackage || null,
        benchSession: benchSession || null,
        displayResult,
        currentStage: STAGES.verify,
        dirty: false,
        intakeComplete: true,
        designEditable: true,
      };
    }

    case ACTIONS.HYDRATE_CURRENT_RESULT: {
      const result = action.result || {};
      const pkg = result.project_package || null;
      const id = resultIdentity(result, pkg);
      return {
        ...state,
        projectId: state.projectId || action.jobId || newProjectId(),
        projectName: id.name || state.projectName,
        goal: id.goal || state.goal,
        mode: id.mode,
        intake: state.intake,
        buildDir: id.dir,
        activeJobId: action.jobId ?? state.activeJobId,
        composeResult: result.compose_result || result.compose || null,
        designQuality: result.design_quality || null,
        agentLoop: result.agent_loop || null,
        projectPackage: pkg,
        benchSession: action.benchSession || result.bench_session || null,
        displayResult: result,
        currentStage: action.stage || STAGES.verify,
        dirty: false,
        intakeComplete: true,
        designEditable: state.designEditable !== false && hasReconstructableGraph(state.graph),
        sessionOrigin: "current_job",
        graph: state.graph,
      };
    }

    case ACTIONS.LOAD_RECENT_BUILD: {
      const result = action.result || {};
      const pkg = result.project_package || null;
      const id = resultIdentity(result, pkg);
      const reconstructable = action.graph || result.studio_graph || null;
      const editable = hasReconstructableGraph(reconstructable);
      return createEmptySession({
        projectId: action.jobId || newProjectId(),
        projectName: id.name,
        goal: id.goal,
        mode: id.mode,
        buildDir: id.dir,
        activeJobId: action.jobId || null,
        composeResult: result.compose_result || result.compose || null,
        designQuality: result.design_quality || null,
        agentLoop: result.agent_loop || null,
        projectPackage: pkg,
        benchSession: action.benchSession || result.bench_session || null,
        displayResult: result,
        currentStage: action.stage || STAGES.verify,
        dirty: false,
        intakeComplete: true,
        designEditable: editable,
        sessionOrigin: "recent_build",
        graph: editable
          ? {
              nodes: reconstructable.nodes || [],
              edges: reconstructable.edges || [],
              phrase: reconstructable.phrase || id.goal || "",
              composeMode: reconstructable.composeMode || "canvas",
            }
          : emptyGraph(id.goal),
      });
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

export function canReturnToDesign(session) {
  return Boolean(session?.designEditable && (session?.graph?.nodes?.length || session?.graph?.phrase));
}

export function sessionHasPackage(session) {
  return Boolean(session?.projectPackage);
}

export function sessionHasBuild(session) {
  return Boolean(session?.buildDir || session?.projectPackage);
}

export function sessionIsResumable(session) {
  return Boolean(session?.projectId);
}
