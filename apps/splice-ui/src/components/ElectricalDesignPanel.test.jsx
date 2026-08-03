import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ElectricalDesignPanel from "./ElectricalDesignPanel.jsx";
import {
  checkElectricalDesign,
  editElectricalDesign,
  projectElectricalDesign,
} from "../projectSession/electricalDesignApi.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";

vi.mock("../projectSession/electricalDesignApi.js", () => ({
  checkElectricalDesign: vi.fn(),
  editElectricalDesign: vi.fn(),
  projectElectricalDesign: vi.fn(),
}));
vi.mock("../projectSession/machineAuthoringApi.js", () => ({
  stageMachineProjectReview: vi.fn(),
}));

const electricalDesign = {
  schema_version: "hardware_splicer.electrical_design.v1",
  design_id: "robot-electrical",
  project_id: "robot",
  components: [
    { component_id: "controller", reference: "U1", name: "Controller", pin_ids: ["controller-vin"], authority: "declared" },
  ],
  pins: [
    {
      pin_id: "controller-vin",
      component_id: "controller",
      number: "1",
      name: "VIN",
      electrical_type: "power_in",
      required: true,
      net_id: null,
      authority: "declared",
    },
  ],
  nets: [],
  power_domains: [],
};

function session(overrides = {}) {
  return {
    projectId: "robot",
    projectName: "Inspection robot",
    goal: "Inspect a building",
    mode: "greenfield",
    graph: { nodes: [], edges: [], phrase: "", composeMode: "canvas" },
    currentStage: "design",
    snapshotRevision: 6,
    persistenceStatus: "saved",
    machineProject: {
      project_id: "robot",
      name: "Inspection robot",
      purpose: "Inspect a building",
      discipline_payloads: {},
    },
    ...overrides,
  };
}

describe("ElectricalDesignPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectElectricalDesign.mockResolvedValue({
      design: electricalDesign,
      erc: {
        clean: false,
        error_count: 1,
        warning_count: 0,
        issues: [
          {
            code: "required_pin_unconnected",
            severity: "error",
            object_id: "controller-vin",
            message: "required pin 'controller-vin' is unconnected",
          },
        ],
      },
    });
    editElectricalDesign.mockResolvedValue({
      design: {
        ...electricalDesign,
        nets: [
          {
            net_id: "vcc",
            name: "VCC",
            kind: "power",
            pin_ids: [],
            authority: "declared",
          },
        ],
      },
      erc: { clean: false, error_count: 1, warning_count: 0, issues: [] },
    });
    stageMachineProjectReview.mockResolvedValue({
      review: { review_id: "review-electrical", base_revision: 6 },
    });
  });

  it("projects the machine and exposes ERC before editing", async () => {
    render(<ElectricalDesignPanel session={session()} onToast={() => {}} />);

    expect(await screen.findByText("required pin unconnected")).toBeInTheDocument();
    expect(screen.getByText(/required pin 'controller-vin' is unconnected/)).toBeInTheDocument();
    expect(projectElectricalDesign).toHaveBeenCalledWith(session().machineProject);
    expect(screen.getByText("1 ERC errors")).toBeInTheDocument();
  });

  it("stages a net candidate as a discipline-payload review", async () => {
    const onToast = vi.fn();
    render(<ElectricalDesignPanel session={session()} onToast={onToast} />);
    await screen.findByText("required pin unconnected");

    fireEvent.change(screen.getByLabelText("Net ID"), { target: { value: "vcc" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "VCC" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "power" } });
    fireEvent.click(screen.getByRole("button", { name: "Run ERC and stage candidate" }));

    await waitFor(() => expect(editElectricalDesign).toHaveBeenCalledTimes(1));
    expect(editElectricalDesign).toHaveBeenCalledWith(electricalDesign, [
      {
        type: "upsert_net",
        payload: {
          net_id: "vcc",
          name: "VCC",
          kind: "power",
          voltage_min_v: null,
          voltage_max_v: null,
          peak_current_a: null,
          authority: "declared",
        },
      },
    ]);
    await waitFor(() => expect(stageMachineProjectReview).toHaveBeenCalledTimes(1));
    const candidateSnapshot = stageMachineProjectReview.mock.calls[0][1];
    expect(candidateSnapshot.machineProject.discipline_payloads.electrical_design.nets[0].net_id).toBe("vcc");
    expect(stageMachineProjectReview.mock.calls[0][2]).toMatchObject({
      baseRevision: 6,
      createdBy: "electrical-author",
      includeMetadata: true,
    });
    expect(screen.getByTestId("electrical-design-staged")).toHaveTextContent("review-electrical");
    expect(onToast).toHaveBeenCalledWith(
      "Electrical candidate staged as review-electrical. Review before acceptance.",
    );
  });

  it("loads a persisted electrical payload instead of re-projecting", async () => {
    checkElectricalDesign.mockResolvedValue({
      design: electricalDesign,
      erc: { clean: true, error_count: 0, warning_count: 0, issues: [] },
    });
    render(
      <ElectricalDesignPanel
        session={session({
          machineProject: {
            ...session().machineProject,
            discipline_payloads: { electrical_design: electricalDesign },
          },
        })}
        onToast={() => {}}
      />,
    );

    await waitFor(() => expect(checkElectricalDesign).toHaveBeenCalledWith(electricalDesign));
    expect(projectElectricalDesign).not.toHaveBeenCalled();
  });
});
