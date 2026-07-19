import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EvidenceWorkbenchPanel from "./EvidenceWorkbenchPanel.jsx";

function session() {
  return {
    mode: "salvage",
    buildDir: "/tmp/build",
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
  });

  it("routes the operator to the existing bench workflow", async () => {
    const user = userEvent.setup();
    const onGoBench = vi.fn();
    render(<EvidenceWorkbenchPanel session={session()} onGoBench={onGoBench} />);
    await user.click(screen.getByRole("button", { name: /record bench evidence/i }));
    expect(onGoBench).toHaveBeenCalledTimes(1);
  });
});
