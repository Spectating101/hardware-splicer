import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MachineEvidencePanel from "./MachineEvidencePanel.jsx";
import { recordMachineEvidence } from "../projectSession/machineEvidenceApi.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";

vi.mock("../projectSession/machineEvidenceApi.js", () => ({
  recordMachineEvidence: vi.fn(),
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
    snapshotRevision: 4,
    persistenceStatus: "saved",
    machineProject: {
      project_id: "robot",
      name: "Inspection robot",
      purpose: "Inspect a building",
      subsystems: [
        { subsystem_id: "power", name: "Power", domain: "electrical", component_ids: ["battery"] },
      ],
      components: [
        {
          component_id: "battery",
          name: "Battery",
          domain: "electrical",
          subsystem_id: "power",
          authority: "declared",
        },
      ],
      requirements: [],
      interfaces: [],
      constraints: [],
      artifacts: [],
    },
    ...overrides,
  };
}

describe("MachineEvidencePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    recordMachineEvidence.mockResolvedValue({
      project: {
        ...session().machineProject,
        components: [
          {
            ...session().machineProject.components[0],
            authority: "measured",
          },
        ],
        evidence: [
          {
            evidence_id: "battery-voltage",
            kind: "multimeter_capture",
            basis: "instrument",
            supports: ["battery"],
            authority: "measured",
            simulated: false,
          },
        ],
      },
    });
    stageMachineProjectReview.mockResolvedValue({
      review: { review_id: "review-evidence", base_revision: 4 },
    });
  });

  it("records physical evidence and stages the authority candidate", async () => {
    const onToast = vi.fn();
    render(<MachineEvidencePanel session={session()} onToast={onToast} />);

    fireEvent.change(screen.getByLabelText("Promotion target"), {
      target: { value: "components|battery" },
    });
    fireEvent.change(screen.getByLabelText("Evidence ID"), {
      target: { value: "battery-voltage" },
    });
    fireEvent.change(screen.getByLabelText("Evidence kind"), {
      target: { value: "multimeter_capture" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage evidence candidate" }));

    await waitFor(() => expect(recordMachineEvidence).toHaveBeenCalledTimes(1));
    expect(recordMachineEvidence).toHaveBeenCalledWith(session().machineProject, {
      evidence: {
        evidence_id: "battery-voltage",
        kind: "multimeter_capture",
        basis: "instrument",
        ref: null,
        supports: ["battery"],
        authority: "measured",
        simulated: false,
      },
      verification: null,
      promotions: [
        { collection: "components", object_id: "battery", authority: "measured" },
      ],
    });
    await waitFor(() => expect(stageMachineProjectReview).toHaveBeenCalledTimes(1));
    expect(stageMachineProjectReview.mock.calls[0][2]).toMatchObject({
      baseRevision: 4,
      createdBy: "evidence-recorder",
    });
    expect(screen.getByTestId("machine-evidence-staged")).toHaveTextContent("review-evidence");
    expect(onToast).toHaveBeenCalledWith(
      "Evidence candidate staged as review-evidence. Review before acceptance.",
    );
  });

  it("shows backend refusal for simulated physical authority", async () => {
    recordMachineEvidence.mockRejectedValue(
      new Error("simulated evidence cannot promote physical target components/battery"),
    );
    render(<MachineEvidencePanel session={session()} onToast={() => {}} />);

    fireEvent.change(screen.getByLabelText("Promotion target"), {
      target: { value: "components|battery" },
    });
    fireEvent.change(screen.getByLabelText("Evidence ID"), {
      target: { value: "battery-sim" },
    });
    fireEvent.click(screen.getByLabelText("Simulated evidence"));
    fireEvent.change(screen.getByLabelText("Proposed target authority"), {
      target: { value: "verified" },
    });
    fireEvent.change(screen.getByLabelText("Verification ID"), {
      target: { value: "verify-battery-sim" },
    });
    fireEvent.change(screen.getByLabelText("Verification name"), {
      target: { value: "Battery simulation" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage evidence candidate" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "simulated evidence cannot promote physical target components/battery",
    );
    expect(stageMachineProjectReview).not.toHaveBeenCalled();
  });

  it("is disabled until a durable revision exists", () => {
    render(
      <MachineEvidencePanel
        session={session({ snapshotRevision: 0, persistenceStatus: "idle" })}
        onToast={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Stage evidence candidate" })).toBeDisabled();
  });
});
