import { createContext, useContext, useMemo, useReducer } from "react";
import {
  ACTIONS,
  createEmptySession,
  projectSessionReducer,
} from "./projectSession.js";

const ProjectSessionContext = createContext(null);

export function ProjectSessionProvider({ children, initialSession }) {
  const [session, dispatch] = useReducer(
    projectSessionReducer,
    initialSession || createEmptySession(),
  );

  const api = useMemo(
    () => ({
      session,
      dispatch,
      reset: () => dispatch({ type: ACTIONS.RESET }),
      startGreenfield: (opts = {}) => dispatch({ type: ACTIONS.START_GREENFIELD, ...opts }),
      startFromIntake: (intake) => dispatch({ type: ACTIONS.START_FROM_INTAKE, intake }),
      setStage: (stage) => dispatch({ type: ACTIONS.SET_STAGE, stage }),
      syncGraph: (patch) => dispatch({ type: ACTIONS.SYNC_GRAPH, ...patch }),
      applyStudioCompile: (payload) =>
        dispatch({ type: ACTIONS.APPLY_STUDIO_COMPILE, ...payload }),
      hydrateBuild: (payload) => dispatch({ type: ACTIONS.HYDRATE_BUILD, ...payload }),
      setBenchSession: (benchSession) =>
        dispatch({ type: ACTIONS.SET_BENCH_SESSION, benchSession }),
      setActiveJob: (jobId) => dispatch({ type: ACTIONS.SET_ACTIVE_JOB, jobId }),
      patchPackageGates: (benchSession) =>
        dispatch({ type: ACTIONS.PATCH_PACKAGE_GATES, benchSession }),
    }),
    [session],
  );

  return (
    <ProjectSessionContext.Provider value={api}>{children}</ProjectSessionContext.Provider>
  );
}

export function useProjectSession() {
  const ctx = useContext(ProjectSessionContext);
  if (!ctx) {
    throw new Error("useProjectSession must be used within ProjectSessionProvider");
  }
  return ctx;
}
