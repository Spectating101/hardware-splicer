import { describe, expect, it } from "vitest";
import { deriveEvidenceTruth } from "./deriveEvidenceTruth.js";

function evidenceSession(overrides = {}) {
  return {
    mode: "salvage",
    buildDir: "/tmp/build",
    displayResult: {
      salvage_package: {
        evidence_integrations: {
          authority: {
            firmware_authorized: false,
            power_authorized: false,
            claim_boundary: "Evidence first.",
          },
          interfaces: [
            {
              compile_status: "blocked",
              blockers: ["signals", "signals.control.voltage_max_v"],
              interface_contract: {
                interface_id: "if:donor:driver",
                virtual_module_id: "donor:board:driver",
                functional_role: "actuator_driver",
                firmware_authorized: false,
                unresolved_fields: ["signals", "signals.control.voltage_max_v"],
              },
            },
          ],
        },
      },
    },
    ...overrides,
  };
}

describe("deriveEvidenceTruth", () => {
  it("blocks firmware when a donor interface is unresolved", () => {
    const truth = deriveEvidenceTruth(evidenceSession());
    expect(truth.applicable).toBe(true);
    expect(truth.state).toBe("blocked");
    expect(truth.interfaceCount).toBe(1);
    expect(truth.unresolvedFieldCount).toBe(2);
    expect(truth.firmwareAuthorized).toBe(false);
    expect(truth.backendReadiness.platformio.state).toBe("blocked");
    expect(truth.backendReadiness.tscircuit.state).toBe("ready");
  });

  it("marks a fully authorized interface verified", () => {
    const session = evidenceSession();
    session.displayResult.salvage_package.evidence_integrations.authority.firmware_authorized = true;
    session.displayResult.salvage_package.evidence_integrations.authority.power_authorized = true;
    session.displayResult.salvage_package.evidence_integrations.interfaces[0] = {
      compile_status: "ready",
      blockers: [],
      interface_contract: {
        interface_id: "if:donor:driver",
        firmware_authorized: true,
        unresolved_fields: [],
      },
    };
    const truth = deriveEvidenceTruth(session);
    expect(truth.state).toBe("verified");
    expect(truth.firmwareAuthorized).toBe(true);
    expect(truth.powerAuthorized).toBe(true);
  });

  it("prefers refreshed Bench authority over the original build snapshot", () => {
    const session = evidenceSession({
      benchSession: {
        power_on_authorized: false,
        evidence_integrations: {
          authority: {
            firmware_authorized: true,
            power_authorized: false,
            claim_boundary: "Updated from typed contract evidence.",
          },
          interfaces: [
            {
              compile_status: "ready",
              blockers: [],
              interface_contract: {
                interface_id: "if:donor:driver",
                firmware_authorized: true,
                unresolved_fields: [],
              },
            },
          ],
        },
      },
    });

    const truth = deriveEvidenceTruth(session);
    expect(truth.state).toBe("bench_required");
    expect(truth.firmwareAuthorized).toBe(true);
    expect(truth.powerAuthorized).toBe(false);
    expect(truth.claimBoundary).toBe("Updated from typed contract evidence.");
  });

  it("creates a conservative fallback for legacy donor rows", () => {
    const truth = deriveEvidenceTruth({
      mode: "salvage",
      displayResult: {
        salvage_package: {
          resolved_modules: [
            {
              source: "donor_functional_salvage",
              module_id: "l298n",
              role: "drv",
              board_id: "legacy-board",
              donor_block_id: "motor-driver",
              connector_refs: ["J1"],
            },
          ],
        },
      },
    });
    expect(truth.state).toBe("blocked");
    expect(truth.interfaces[0].legacy_fallback).toBe(true);
    expect(truth.interfaces[0].interface_contract.firmware_authorized).toBe(false);
  });

  it("stays out of greenfield projects", () => {
    const truth = deriveEvidenceTruth({ mode: "greenfield" });
    expect(truth.applicable).toBe(false);
    expect(truth.state).toBe("not_applicable");
  });
});
