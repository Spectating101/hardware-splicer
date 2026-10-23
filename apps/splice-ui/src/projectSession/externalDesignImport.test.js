import { describe, expect, it } from "vitest";
import { importOpenBlueprintDesignPackage } from "./externalDesignImport.js";

function fixture() {
  return {
    name: "RC rover from donors",
    summary: "Reference only",
    tags: ["ROVER"],
    parts: [
      { id: "left", name: "Recovered motor A", category: "actuator", domain: "electrical", role: "Drive", description: "Uncharacterized", qty: 1, unitCost: 0, pins: ["P", "N"] },
      { id: "right", name: "Recovered motor B", category: "actuator", domain: "electrical", role: "Drive", description: "Uncharacterized", qty: 1, unitCost: 0, pins: ["P", "N"] },
      { id: "driver", name: "Unknown donor board", category: "module", domain: "electrical", role: "Control", description: "Unknown electrical limits", qty: 1, unitCost: 0, pins: ["M1+", "M1-"] },
    ],
    connections: [
      { id: "c1", from: { part: "driver", pin: "M1+" }, to: { part: "left", pin: "P" }, net: "power" },
    ],
    assembly: [{ part: "driver", children: [{ part: "left" }, { part: "right" }] }],
    tools: ["multimeter"],
    assumptions: ["Driver power voltage not characterized"],
    instructions: [{ id: "first", title: "Measure", steps: [{ id: "1", title: "Inspect", detail: "Do not power yet", tools: ["multimeter"], parts: ["driver"] }] }],
  };
}

describe("external OpenBlueprint design import (reference-only)", () => {
  it("preserves both donor motors, original assumptions and missing voltage", () => {
    const original = fixture();
    const result = importOpenBlueprintDesignPackage(original);
    expect(result.partLines.filter((p) => p.name.includes("Recovered motor"))).toHaveLength(2);
    expect(result.partLines.map((p) => p.quantity)).toEqual([1, 1, 1]);
    expect(JSON.stringify(result)).not.toContain("7.4");
    expect(JSON.stringify(result)).not.toContain("12 V");
    expect(result.assumptions).toEqual(original.assumptions);
    expect(result.estimatedBomTotalUsd).toBe(0);
    expect(original.parts[0].qty).toBe(1);
  });
  it("never grants HS package, DRC or physical authorization", () => {
    const output = importOpenBlueprintDesignPackage(fixture());
    expect(output.hsProjectPackage).toBeNull();
    expect(output.validation).toMatchObject({
      engineeringValid: false, drcChecked: false, benchAuthorized: false,
      powerOnAuthorized: false, fabricationAuthorized: false, buildReady: false,
      sourceIdentityVerified: false,
    });
    expect(output.proposedConnections[0].verified).toBe(false);
    expect(output.source.contentSha256).toBeNull();
    expect(output.source.contentLicense).toBeNull();
  });
  it("rejects invented or undeclared pin references", () => {
    const input = fixture();
    input.connections[0].to.pin = "FAKE";
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/undeclared pin/);
  });
  it("rejects external graph references to absent parts", () => {
    const input = fixture();
    input.connections[0].to.part = "nonexistent";
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/unknown part/);
  });
  it("rejects duplicate part identities and invalid quantity", () => {
    const input = fixture();
    input.parts[1].id = "left";
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/duplicate part/);
    input.parts[1].id = "right";
    input.parts[0].qty = 0;
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/positive integer/);
  });
  it("rejects unknown assembly or instruction part references", () => {
    const input = fixture();
    input.assembly[0].children.push({ part: "missing" });
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/assembly references unknown/);
    input.assembly[0].children.pop();
    input.instructions[0].steps[0].parts.push("missing");
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/instructions reference unknown/);
  });
  it("rejects malformed or unbounded source objects", () => {
    expect(() => importOpenBlueprintDesignPackage({ parts: [] })).toThrow(/name/);
    const input = fixture();
    input.connections = Array.from({ length: 4001 }, (_, i) => ({ id: String(i) }));
    expect(() => importOpenBlueprintDesignPackage(input)).toThrow(/at most 4000/);
  });
});
