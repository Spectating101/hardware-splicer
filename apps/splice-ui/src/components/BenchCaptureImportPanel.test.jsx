import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BenchCaptureImportPanel from "./BenchCaptureImportPanel.jsx";
import { projectBenchCaptureEvidence } from "../projectSession/benchCaptureEvidenceApi.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";

vi.mock("../projectSession/benchCaptureEvidenceApi.js", () => ({
  projectBenchCaptureEvidence: vi.fn(),
}));
vi.mock("../projectSession/machineAuthoringApi.js", () => ({
  stageMachineProjectReview: vi.fn(),
}));

function session(overrides = {}) {
  return {
    projectId: "robot",
    projectName: "Inspection robot",
    goal: "Inspect a building",
    mode: "greenfield",
    graph: { nodes: [], edges: [], phrase: "", composeMode: "canvas" },
    currentStage: "verify",
    snapshotRevision: 5,
    persistenceStatus: "saved",
    machineProject: {
      project_id: "robot",
      name: "Inspection robot",
      purpose: "Inspect a building",
      subsystems: [{ subsystem_id: "power", name: "Power", domain: "electrical" }],
      components: [],
      interfaces: [],
    },
    ...overrides,
  };
}

const capture = {
  schema_version: "bench_topology_capture.v1",
  capture_id: "power-load-001",
  measurements: [
    {
      gate_id: "gate-power",
      status: "pass",
      value: 12.1,
      unit: "V",
      instrument_id: "dmm-1",
    },
  ],
};

describe("BenchCaptureImportPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectBenchCaptureEvidence.mockResolvedValue({
      project: {
        ...session().machineProject,
        evidence: [{ evidence_id: "bench-power-load-001-gate-power" }],
      },
      bench_capture: {
        capture_id: "power-load-001",
        capture_sha256: "abc123",
        imported_count: 1,
        measurement_count: 1,
        warnings: [
          {
            code: "measurement_authority_limited",
            measurement: "gate-power",
            message: "instrument calibration limited authority to observed",
          },
        ],
      },
    });
    stageMachineProjectReview.mockResolvedValue({
      review: { review_id: "review-capture", base_revision: 5 },
    });
  });

  it("projects capture evidence and stages a review candidate", async () => {
    const onToast = vi.fn();
    render(<BenchCaptureImportPanel session={session()} onToast={onToast} />);

    fireEvent.change(screen.getByLabelText("`bench_topology_capture.v1` JSON"), {
      target: { value: JSON.stringify(capture) },
    });
    fireEvent.change(screen.getByLabelText("Explicit target map JSON"), {
      target: {
        value: JSON.stringify({
          "gate-power": { collection: "subsystems", object_id: "power" },
        }),
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage capture evidence" }));

    await waitFor(() => expect(projectBenchCaptureEvidence).toHaveBeenCalledTimes(1));
    expect(projectBenchCaptureEvidence).toHaveBeenCalledWith(
      session().machineProject,
      capture,
      { "gate-power": { collection: "subsystems", object_id: "power" } },
    );
    await waitFor(() => expect(stageMachineProjectReview).toHaveBeenCalledTimes(1));
    expect(stageMachineProjectReview.mock.calls[0][2]).toMatchObject({
      baseRevision: 5,
      createdBy: "bench-capture-importer",
      note: "Import bench capture power-load-001",
    });
    expect(screen.getByTestId("bench-capture-import-result")).toHaveTextContent("abc123");
    expect(screen.getByTestId("bench-capture-import-result")).toHaveTextContent(
      "measurement authority limited",
    );
    expect(screen.getByTestId("bench-capture-staged")).toHaveTextContent("review-capture");
    expect(onToast).toHaveBeenCalledWith(
      "Bench capture staged as review-capture. Review before acceptance.",
    );
  });

  it("rejects invalid capture JSON before calling the API", async () => {
    render(<BenchCaptureImportPanel session={session()} onToast={() => {}} />);
    fireEvent.change(screen.getByLabelText("`bench_topology_capture.v1` JSON"), {
      target: { value: "not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage capture evidence" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Bench capture must be valid JSON");
    expect(projectBenchCaptureEvidence).not.toHaveBeenCalled();
  });

  it("is disabled before the project has a durable revision", () => {
    render(
      <BenchCaptureImportPanel
        session={session({ snapshotRevision: 0, persistenceStatus: "idle" })}
        onToast={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("`bench_topology_capture.v1` JSON"), {
      target: { value: JSON.stringify(capture) },
    });
    expect(screen.getByRole("button", { name: "Stage capture evidence" })).toBeDisabled();
  });
});
