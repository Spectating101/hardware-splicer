import { act, renderHook, waitFor } from "@testing-library/react";
import { useReducer } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useProjectPersistence } from "./projectPersistence.js";
import { ACTIONS, canonicalJson, createEmptySession, projectSessionReducer } from "./projectSession.js";

// The backend returns snapshots with sorted keys and whatever runtime flags the last save carried.
function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortKeys(value[key])]));
  }
  return value;
}

const MACHINE = { project_id: "drone-build", components: [], constraints: [], artifacts: [] };
const STORED = {
  // A full snapshot as an earlier save stored it: sorted keys, dirty left true by the old seed.
  full: sortKeys({ ...createEmptySession({ projectId: "drone-build", projectName: "Drone build", goal: "Fly",
    intake: { goal: "Fly", project_name: "Drone build" }, machineProject: MACHINE }), dirty: true, sessionOrigin: "new",
  snapshotRevision: undefined, persistenceStatus: undefined, persistenceError: undefined, savedAt: undefined,
  restoredFromRevision: undefined }),
  // A legacy snapshot written by a script: no defaults and no machine model.
  legacy: { projectId: "drone-build", projectName: "Drone build", mode: "greenfield", goal: "Fly",
    intake: { goal: "Fly", project_name: "Drone build" }, constraints: { location: "Taiwan" } },
};

function stubBackend(snapshot) {
  const fetchMock = vi.fn(async (url, options = {}) => {
    const text = String(url);
    let body = { projects: [] };
    if (options.method === "PUT") body = { project: { revision: 99, saved_at: "now" } };
    else if (text.includes("/machine-projects/from-intake")) body = { project: MACHINE };
    else if (/\/v1\/projects\/drone-build(\?|$)/.test(text)) {
      body = { project: { project_id: "drone-build", revision: 2, saved_at: "then", snapshot } };
    }
    return { ok: true, status: 200, json: async () => body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function useHarness() {
  const [session, dispatch] = useReducer(projectSessionReducer, undefined, () => createEmptySession());
  const persistence = useProjectPersistence({ session, dispatch, debounceMs: 20 });
  return { session, dispatch, persistence };
}

const puts = (fetchMock) => fetchMock.mock.calls.filter(([, options]) => options?.method === "PUT");

afterEach(() => vi.unstubAllGlobals());

describe("reopening a saved project", () => {
  it.each(["full", "legacy"])("never writes a revision when a %s snapshot is opened again and again", async (kind) => {
    const fetchMock = stubBackend(STORED[kind]);
    const { result } = renderHook(() => useHarness());
    for (let open = 0; open < 4; open += 1) {
      await act(async () => { await result.current.persistence.openProject("drone-build"); });
      await waitFor(() => expect(result.current.session.machineProject).toEqual(MACHINE));
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 80)); });
    }
    expect(puts(fetchMock)).toEqual([]);
    expect(result.current.session.snapshotRevision).toBe(2);
    expect(result.current.session.dirty).toBe(false);
  });

  it("still saves a real edit, once, carrying the derived machine model", async () => {
    const fetchMock = stubBackend(STORED.legacy);
    const { result } = renderHook(() => useHarness());
    await act(async () => { await result.current.persistence.openProject("drone-build"); });
    await waitFor(() => expect(result.current.session.machineProject).toEqual(MACHINE));
    act(() => result.current.dispatch({ type: ACTIONS.SET_STAGE, stage: "design" }));
    await waitFor(() => expect(puts(fetchMock)).toHaveLength(1));
    const saved = JSON.parse(puts(fetchMock)[0][1].body);
    expect(saved.expected_revision).toBe(2);
    expect(saved.snapshot.currentStage).toBe("design");
    expect(saved.snapshot.machineProject).toEqual(MACHINE);
  });
});

describe("canonicalJson", () => {
  it("ignores key order and undefined members like JSON does", () => {
    expect(canonicalJson({ b: 1, a: { d: [1, { y: 2, x: undefined }], c: null } }))
      .toBe(canonicalJson({ a: { c: null, d: [1, { y: 2 }] }, b: 1 }));
    expect(canonicalJson({ a: 1 })).not.toBe(canonicalJson({ a: 2 }));
  });
});
