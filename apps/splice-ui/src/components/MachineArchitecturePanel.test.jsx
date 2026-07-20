import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MachineArchitecturePanel, { projectIssues } from "./MachineArchitecturePanel.jsx";

const project = {
  schema_version: "hardware_splicer.machine_project.v1",
  project_id: "inspection-robot",
  name: "Inspection robot",
  purpose: "Inspect a building",
  lifecycle_state: "architecture",
  requested_release_state: "concept",
  requirements: [
    {
      requirement_id: "req-runtime",
      statement: "Operate for 90 minutes",
      kind: "performance",
      allocated_to: ["power-system"],
      verification_method_ids: [],
      authority: "declared",
    },
  ],
  subsystems: [
    {
      subsystem_id: "system",
      name: "Machine system",
      domain: "system",
      purpose: "Inspect a building",
      requirement_ids: ["req-runtime"],
      component_ids: [],
    },
    {
      subsystem_id: "power-system",
      name: "Power system",
      domain: "electrical",
      purpose: "Deliver energy",
      requirement_ids: ["req-runtime"],
      component_ids: ["battery"],
    },
    {
      subsystem_id: "drive-system",
      name: "Drive system",
      domain: "mechanical",
      purpose: "Move the machine",
      component_ids: ["motor"],
    },
  ],
  components: [
    {
      component_id: "battery",
      name: "Battery pack",
      subsystem_id: "power-system",
      domain: "electrical",
      role: "power source",
      source: "new",
      authority: "declared",
    },
    {
      component_id: "motor",
      name: "Drive motor",
      subsystem_id: "drive-system",
      domain: "mechanical",
      role: "actuator",
      source: "donor",
      authority: "declared",
    },
  ],
  interfaces: [
    {
      interface_id: "motor-power",
      name: "Motor power",
      kind: "power",
      authority: "unknown",
      endpoints: [
        { object_id: "battery", port: "output" },
        { object_id: "motor", port: "input" },
      ],
      contracts: [
        {
          contract_type: "electrical",
          unresolved_fields: ["peak_current"],
        },
      ],
    },
  ],
  verifications: [],
};

describe("MachineArchitecturePanel", () => {
  it("shows purpose, subsystem counts, and conservative traceability gaps", () => {
    render(<MachineArchitecturePanel project={project} />);

    expect(screen.getByText("Inspection robot")).toBeInTheDocument();
    expect(screen.getByText("Inspect a building")).toBeInTheDocument();
    expect(screen.getByLabelText("Machine project counts")).toHaveTextContent("3 subsystems");
    expect(screen.getByText("Unverified Requirement")).toBeInTheDocument();
    expect(screen.getByText("Unresolved Interface")).toBeInTheDocument();
    expect(screen.getByText(/does not imply fabrication/i)).toBeInTheDocument();
  });

  it("navigates subsystems and offers the matching discipline workspace", () => {
    const onOpenDiscipline = vi.fn();
    render(
      <MachineArchitecturePanel project={project} onOpenDiscipline={onOpenDiscipline} />,
    );

    expect(screen.getByText("Battery pack")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("machine-subsystem-drive-system"));
    expect(screen.getByText("Drive motor")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Mechanical workspace" }));
    expect(onOpenDiscipline).toHaveBeenCalledWith(
      "mechanical",
      expect.objectContaining({ subsystem_id: "drive-system" }),
    );
  });

  it("does not pretend an absent machine object exists", () => {
    render(<MachineArchitecturePanel project={null} />);
    expect(screen.getByTestId("machine-architecture-empty")).toHaveTextContent(
      "Finish Intake",
    );
  });
});

describe("projectIssues", () => {
  it("returns no gaps when requirements and interfaces are closed", () => {
    expect(
      projectIssues({
        requirements: [{ requirement_id: "r1", verification_method_ids: ["v1"] }],
        interfaces: [
          {
            interface_id: "i1",
            contracts: [{ unresolved_fields: [] }],
          },
        ],
      }),
    ).toEqual([]);
  });
});
