import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MachineAuthoringPanel from "./MachineAuthoringPanel.jsx";
import {
  editMachineProject,
  stageMachineProjectReview,
} from "../projectSession/machineAuthoringApi.js";

vi.mock("../projectSession/machineAuthoringApi.js", () => ({
  editMachineProject: vi.fn(),
  stageMachineProjectReview: vi.fn(),
}));

function session(overrides = {}) {
  return {
    projectId: "robot",
    projectName: "Inspection robot",
    goal: "Inspect a building",
    mode: "greenfield",
    graph: { nodes: [], edges: [], phrase: "", composeMode: "canvas" },
    machineProject: {
      project_id: "robot",
      name: "Inspection robot",
      purpose: "Inspect a building",
      subsystems: [
        { subsystem_id: "control", name: "Control", domain: "firmware" },
        { subsystem_id: "drive", name: "Drive", domain: "mechanical" },
      ],
      components: [],
      interfaces: [],
    },
    currentStage: "design",
    snapshotRevision: 3,
    persistenceStatus: "saved",
    ...overrides,
  };
}

describe("MachineAuthoringPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    editMachineProject.mockResolvedValue({
      project: {
        ...session().machineProject,
        requirements: [
          {
            requirement_id: "req-runtime",
            statement: "The robot shall operate for 90 minutes.",
            kind: "performance",
            allocated_to: ["control"],
            authority: "declared",
          },
        ],
      },
    });
    stageMachineProjectReview.mockResolvedValue({
      review: { review_id: "review-123", base_revision: 3 },
    });
  });

  it("validates a requirement and stages the candidate instead of mutating the session", async () => {
    const onToast = vi.fn();
    render(<MachineAuthoringPanel session={session()} onToast={onToast} />);

    fireEvent.change(screen.getByLabelText("Requirement ID"), {
      target: { value: "req-runtime" },
    });
    fireEvent.change(screen.getByLabelText("Statement"), {
      target: { value: "The robot shall operate for 90 minutes." },
    });
    fireEvent.change(screen.getByLabelText("Kind"), {
      target: { value: "performance" },
    });
    fireEvent.change(screen.getByLabelText("Allocate to"), {
      target: { value: "control" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage candidate for review" }));

    await waitFor(() => expect(editMachineProject).toHaveBeenCalledTimes(1));
    expect(editMachineProject.mock.calls[0][1]).toEqual([
      {
        type: "upsert_requirement",
        payload: {
          requirement_id: "req-runtime",
          statement: "The robot shall operate for 90 minutes.",
          kind: "performance",
          allocated_to: ["control"],
          authority: "declared",
        },
      },
    ]);
    await waitFor(() => expect(stageMachineProjectReview).toHaveBeenCalledTimes(1));
    expect(stageMachineProjectReview.mock.calls[0][0]).toBe("robot");
    expect(stageMachineProjectReview.mock.calls[0][2].baseRevision).toBe(3);
    expect(screen.getByTestId("machine-authoring-staged")).toHaveTextContent("review-123");
    expect(onToast).toHaveBeenCalledWith(
      "Candidate staged as review-123. Review it before acceptance.",
    );
  });

  it("creates the first declared interface with unresolved contract fields", async () => {
    render(<MachineAuthoringPanel session={session()} onToast={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "New interface" }));
    fireEvent.change(screen.getByLabelText("Interface ID"), { target: { value: "control-link" } });
    fireEvent.change(screen.getByLabelText("Interface name"), { target: { value: "Control link" } });
    fireEvent.change(screen.getByLabelText("Interface kind"), { target: { value: "control" } });
    fireEvent.change(screen.getByLabelText("Source object"), { target: { value: "control" } });
    fireEvent.change(screen.getByLabelText("Source port"), { target: { value: "command" } });
    fireEvent.change(screen.getByLabelText("Target object"), { target: { value: "drive" } });
    fireEvent.change(screen.getByLabelText("Target port"), { target: { value: "enable" } });
    fireEvent.change(screen.getByLabelText("Contract values (JSON)"), {
      target: { value: '{"logic_voltage_v":3.3}' },
    });
    fireEvent.change(screen.getByLabelText("Unresolved fields"), {
      target: { value: "pin_mapping, timing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Stage candidate for review" }));

    await waitFor(() => expect(editMachineProject).toHaveBeenCalledTimes(1));
    expect(editMachineProject.mock.calls[0][1]).toEqual([
      {
        type: "upsert_interface",
        payload: {
          interface_id: "control-link",
          name: "Control link",
          kind: "control",
          endpoints: [
            { object_id: "control", port: "command", role: "source" },
            { object_id: "drive", port: "enable", role: "target" },
          ],
          contracts: [
            {
              contract_type: "electrical",
              values: { logic_voltage_v: 3.3 },
              unresolved_fields: ["pin_mapping", "timing"],
              authority: "declared",
            },
          ],
          authority: "declared",
        },
      },
    ]);
  });

  it("refuses to stage against an unsaved workspace", () => {
    render(
      <MachineAuthoringPanel
        session={session({ snapshotRevision: 0, persistenceStatus: "idle" })}
        onToast={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Stage candidate for review" })).toBeDisabled();
  });
});
