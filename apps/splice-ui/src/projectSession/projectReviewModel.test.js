import { describe, expect, it } from "vitest";
import { createEmptySession } from "./projectSession.js";
import { deriveProjectReview } from "./projectReviewModel.js";

describe("product review projection", () => {
  it("shows real greenfield package data and labels software checks without physical promotion", () => {
    const hash = "a".repeat(64);
    const session = createEmptySession({
      projectId: "project-a",
      projectName: "Sensor fixture",
      goal: "Build a sensor fixture",
      mode: "greenfield",
      snapshotRevision: 3,
      intakeComplete: true,
      projectPackage: {
        build_dir: "/tmp/sensor",
        info: { project_revision: 3 },
        bom: { lines: [{ ref: "U1", description: "Sensor", qty: 1 }] },
        source_descriptors: [{ source_id: "datasheet", content_hash: hash }],
        gates: { compile_ok: true, blockers: ["Pin voltage unverified"] },
      },
    });
    const review = deriveProjectReview(session);
    expect(review.name).toBe("Sensor fixture");
    expect(review.parts).toHaveLength(1);
    expect(review.sources).toEqual([{ id: "datasheet", sha256: hash }]);
    expect(review.softwareCheck).toBe("Checked in software");
    expect(review.physicalCheck).toBe("Not established by this review");
    expect(review.blockers).toEqual(["Pin voltage unverified"]);
    expect(review.revisionBound).toBe(true);
  });

  it("leaves donor specifications and missing source hashes unknown", () => {
    const session = createEmptySession({
      projectId: "project-b",
      mode: "salvage",
      intakeComplete: true,
      projectPackage: {
        info: { project_name: "RC toy rover" },
        bom: { lines: [{ description: "Donor DC motor", qty: 2 }] },
        sources: [{ source_id: "seller listing", content_hash: "not-a-hash" }],
        gates: { compile_ok: false },
      },
      benchSession: { physical_capture: true, power_on_authorized: true },
    });
    const review = deriveProjectReview(session);
    expect(review.mode).toBe("Reuse / donor hardware");
    expect(review.sources).toEqual([]);
    expect(review.softwareCheck).toBe("Check failed");
    expect(review.physicalCheck).toBe("Not established by this review");
    expect(review.revisionBound).toBe(false);
    expect(review.parts[0]).not.toHaveProperty("voltage_v");
    expect(review.parts[0]).not.toHaveProperty("current_a");
  });
});
