import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EvidenceWorkbenchPanel from "./EvidenceWorkbenchPanel.jsx";

function session() {
  return {
    mode: "salvage",
    buildDir: "/tmp/build",
    benchSession: {
      open_gates: [
        {
          gate_id: "evidence_if_enabot_driver_field_signals",
          interface_id: "if:enabot:driver",
          evidence_field: "signals",
          requires_contract_edit: true,
          status: "open",
        },
      ],
      power_on_authorized: false,
    },
    displayResult: {
      salvage_package: {
        evidence_integrations: {
          authority: {
            firmware_authorized: false,
            power_authorized: false,
            claim_boundary: "No interface claim without accepted evidence.",
          },
          interfaces: [
            {
              compile_status: "blocked",
              blockers: ["signals"],
              interface_contract: {
                interface_id: "if:enabot:driver",
                virtual_module_id: "donor:enabot:driver",
                board_id: "enabot",
                block_id: "driver",
                functional_role: "actuator_driver",
                status: "partial",
                contacts: [{ contact_id: "J1.unknown", connector_ref: "J1" }],
                signals: [],
                reference_equivalents: [
                  {
                    module_id: "l298n",
                    relationship: "functional_analogy_only",
                    electrical_contract_inherited: false,
                  },
                ],
                unresolved_fields: ["signals"],
                firmware_authorized: false,
              },
              bench_recipe: {
                phases: [
                  {
                    phase_id: "identify_ground",
                    title: "Identify ground contacts",
                    instructions: ["Keep the donor unpowered."],
                    measurements: [
                      {
                        measurement_id: "ground_resistance_ohm",
                        description: "Resistance to known ground",
                        unit: "ohm",
                      },
                    ],
                  },
                ],
              },
            },
          ],
        },
      },
    },
  };
}

describe("EvidenceWorkbenchPanel", () => {
  it("renders authority boundaries and reference-only analogies", () => {
    render(<EvidenceWorkbenchPanel session={session()} />);
    expect(screen.getByTestId("evidence-workbench")).toBeInTheDocument();
    expect(screen.getByText(/donor interface.*blocked/i)).toBeInTheDocument();
    expect(screen.getByText("l298n")).toBeInTheDocument();
    expect(screen.getByText(/electrical pins and limits are not inherited/i)).toBeInTheDocument();
    expect(screen.getByText("Identify ground contacts")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-contract-editor")).toBeInTheDocument();
  });

  it("routes the operator to the existing bench workflow", async () => {
    const user = userEvent.setup();
    const onGoBench = vi.fn();
    render(<EvidenceWorkbenchPanel session={session()} onGoBench={onGoBench} />);
    await user.click(screen.getByRole("button", { name: /record bench evidence/i }));
    expect(onGoBench).toHaveBeenCalledTimes(1);
  });

  it("submits a typed, provenance-bearing interface contract update", async () => {
    const user = userEvent.setup();
    const onContractUpdate = vi.fn().mockResolvedValue({
      last_submission: { applied: [{ ok: true, contract_update: true }] },
    });
    render(
      <EvidenceWorkbenchPanel
        session={session()}
        onContractUpdate={onContractUpdate}
      />,
    );

    await user.clear(screen.getByLabelText(/contact id/i));
    await user.type(screen.getByLabelText(/contact id/i), "J1.1");
    await user.type(screen.getByLabelText(/physical pin/i), "1");
    await user.type(screen.getByLabelText(/controller pin/i), "GPIO16");
    await user.click(screen.getByRole("button", { name: /save evidenced signal/i }));

    expect(onContractUpdate).toHaveBeenCalledTimes(1);
    const [measurements] = onContractUpdate.mock.calls[0];
    expect(measurements[0].gate_id).toBe("evidence_if_enabot_driver_field_signals");
    expect(measurements[0].contract_update).toMatchObject({
      operation: "upsert_signal",
      interface_id: "if:enabot:driver",
      signal_id: "enable",
      contact_id: "J1.1",
      direction: "input",
      voltage_max_v: 3.3,
      active_level: "high",
      controller_pin: "GPIO16",
      producer: "operator+instrument",
    });
    expect(await screen.findByText(/interface contract persisted/i)).toBeInTheDocument();
  });
});
