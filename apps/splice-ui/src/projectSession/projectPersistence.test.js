import { afterEach, describe, expect, it, vi } from "vitest";
import {
  archivePersistentProject,
  deletePersistentProject,
  duplicatePersistentProject,
  listPersistentProjects,
  loadPersistentProject,
  savePersistentProject,
} from "./projectPersistence.js";

function jsonResponse(body, { ok = true, status = 200, statusText = "OK" } = {}) {
  return {
    ok,
    status,
    statusText,
    json: vi.fn().mockResolvedValue(body),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("persistent project API client", () => {
  it("saves a snapshot with optimistic revision metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ project: { project_id: "robot", revision: 4 } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await savePersistentProject(
      "robot",
      { projectId: "robot", projectName: "Robot" },
      { expectedRevision: 3, metadata: { client: "test" } },
    );

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/projects/robot/snapshot");
    expect(options.method).toBe("PUT");
    expect(JSON.parse(options.body)).toEqual({
      snapshot: { projectId: "robot", projectName: "Robot" },
      expected_revision: 3,
      metadata: { client: "test" },
    });
  });

  it("lists, loads, duplicates, archives, and deletes project resources", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true, projects: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await listPersistentProjects({ includeArchived: true });
    await loadPersistentProject("robot drive", { revision: 2 });
    await duplicatePersistentProject("robot drive", "robot-copy");
    await archivePersistentProject("robot drive", true);
    await deletePersistentProject("robot drive");

    expect(fetchMock.mock.calls[0][0]).toContain("include_archived=true");
    expect(fetchMock.mock.calls[1][0]).toContain("robot%20drive?revision=2");
    expect(fetchMock.mock.calls[2][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      target_project_id: "robot-copy",
    });
    expect(fetchMock.mock.calls[3][1].method).toBe("PATCH");
    expect(fetchMock.mock.calls[4][1].method).toBe("DELETE");
  });

  it("preserves conflict status on API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: { type: "revision_conflict", message: "stale revision" } },
          { ok: false, status: 409, statusText: "Conflict" },
        ),
      ),
    );

    await expect(
      savePersistentProject("robot", {}, { expectedRevision: 1 }),
    ).rejects.toMatchObject({
      status: 409,
      type: "revision_conflict",
      message: "stale revision",
    });
  });
});
