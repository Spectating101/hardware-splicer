import { afterEach, describe, expect, it, vi } from "vitest";
import { seedMachineProjectFromIntake } from "./projectPersistence.js";

function response(body, { ok = true, status = 200, statusText = "OK" } = {}) {
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

describe("machine project persistence bridge", () => {
  it("seeds the canonical machine object through the product API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        ok: true,
        project: {
          schema_version: "hardware_splicer.machine_project.v1",
          project_id: "inspection-robot",
          purpose: "Inspect a building",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await seedMachineProjectFromIntake({
      project_name: "inspection-robot",
      goal: "Inspect a building",
    });

    expect(result.project.project_id).toBe("inspection-robot");
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toContain("/v1/machine-projects/from-intake");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      intake: {
        project_name: "inspection-robot",
        goal: "Inspect a building",
      },
    });
  });

  it("does not disguise machine seeding failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response(
          { detail: { type: "invalid_machine_intake", message: "invalid intake" } },
          { ok: false, status: 422, statusText: "Unprocessable Entity" },
        ),
      ),
    );

    await expect(seedMachineProjectFromIntake({})).rejects.toMatchObject({
      status: 422,
      type: "invalid_machine_intake",
      message: "invalid intake",
    });
  });
});
