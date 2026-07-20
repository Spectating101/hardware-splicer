import { describe, expect, it } from "vitest";
import {
  ACTIONS,
  PERSISTENCE_STATUS,
  createEmptySession,
  projectSessionReducer,
  projectSnapshot,
  sessionIsPersistable,
} from "./projectSession.js";


describe("persistent project session state", () => {
  it("restores a server snapshot without promoting or dirtying it", () => {
    const restored = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.RESTORE_PROJECT_SNAPSHOT,
      projectId: "robot",
      revision: 7,
      savedAt: "2026-07-20T00:00:00Z",
      recovered: true,
      snapshot: {
        projectId: "robot",
        projectName: "Inspection robot",
        goal: "Inspect the workshop",
        mode: "salvage",
        currentStage: "verify",
        graph: { nodes: [{ id: "controller" }], edges: [], phrase: "robot", composeMode: "canvas" },
        benchSession: { power_on_authorized: false },
      },
    });

    expect(restored.projectId).toBe("robot");
    expect(restored.snapshotRevision).toBe(7);
    expect(restored.persistenceStatus).toBe(PERSISTENCE_STATUS.restored);
    expect(restored.restoredFromRevision).toBe(7);
    expect(restored.dirty).toBe(false);
    expect(restored.benchSession.power_on_authorized).toBe(false);
    expect(restored.sessionOrigin).toBe("persistent_project");
  });

  it("tracks saving, saved, conflict, and failure state independently of design state", () => {
    let state = createEmptySession({ projectId: "robot", projectName: "Robot" });
    state = projectSessionReducer(state, {
      type: ACTIONS.SET_PERSISTENCE,
      status: PERSISTENCE_STATUS.saving,
    });
    expect(state.persistenceStatus).toBe("saving");

    state = projectSessionReducer(state, {
      type: ACTIONS.SET_PERSISTENCE,
      status: PERSISTENCE_STATUS.saved,
      revision: 3,
      savedAt: "now",
    });
    expect(state.snapshotRevision).toBe(3);
    expect(state.savedAt).toBe("now");

    state = projectSessionReducer(state, {
      type: ACTIONS.SET_PERSISTENCE,
      status: PERSISTENCE_STATUS.conflict,
      error: "stale writer",
    });
    expect(state.persistenceStatus).toBe("conflict");
    expect(state.persistenceError).toBe("stale writer");
  });

  it("serializes engineering state without transient persistence metadata", () => {
    const state = createEmptySession({
      projectId: "robot",
      projectName: "Robot",
      snapshotRevision: 4,
      persistenceStatus: PERSISTENCE_STATUS.saved,
      persistenceError: "old error",
      savedAt: "yesterday",
      restoredFromRevision: 3,
      machineProject: { schema_version: "hardware_splicer.machine_project.v1" },
    });

    const snapshot = projectSnapshot(state);
    expect(snapshot.projectId).toBe("robot");
    expect(snapshot.machineProject.schema_version).toBe("hardware_splicer.machine_project.v1");
    expect(snapshot).not.toHaveProperty("snapshotRevision");
    expect(snapshot).not.toHaveProperty("persistenceStatus");
    expect(snapshot).not.toHaveProperty("persistenceError");
    expect(snapshot).not.toHaveProperty("savedAt");
    expect(snapshot).not.toHaveProperty("restoredFromRevision");
  });

  it("stores a canonical machine project inside the same project session", () => {
    let state = createEmptySession({ projectId: "robot", projectName: "Robot" });
    state = projectSessionReducer(state, {
      type: ACTIONS.SET_MACHINE_PROJECT,
      machineProject: {
        schema_version: "hardware_splicer.machine_project.v1",
        project_id: "robot",
        purpose: "Inspect a building",
      },
    });

    expect(state.machineProject.project_id).toBe("robot");
    expect(state.dirty).toBe(true);
    expect(sessionIsPersistable(state)).toBe(true);
  });
});
