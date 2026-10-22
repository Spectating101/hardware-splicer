import { describe, expect, it } from "vitest";
import {
  normalizeHsProjectPackage, normalizeOpenBlueprintDesign,
} from "./designPackage.js";

const sample = () => ({
  name: "Workshop sensor",
  summary: "A Pico reads temperature and drives a display.",
  tags: ["SENSOR"],
  parts: [
    { id: "pico", name: "Raspberry Pi Pico", role: "Controller", category: "mcu",
      domain: "electrical", qty: 1, unitCost: 5, pins: ["3V3", "GND", "GP4"] },
    { id: "sensor", name: "I2C sensor", role: "Sense", category: "sensor",
      domain: "electrical", qty: 1, unitCost: 4, pins: ["VCC", "GND", "SDA"] },
    { id: "case", name: "Case", role: "Protect", category: "enclosure",
      domain: "mechanical", qty: 1, unitCost: 0, pins: [] },
  ],
  connections: [
    { id: "wire-1", from: { part: "pico", pin: "3V3" },
      to: { part: "sensor", pin: "VCC" }, net: "power", label: "3V3" },
  ],
  assembly: [{ part: "case", children: [{ part: "pico" }, { part: "sensor" }] }],
  tools: ["screwdriver"], assumptions: ["I2C address unconfirmed"],
  instructions: [{ id: "assembly", title: "Assembly", steps: [{
    id: "1.1", title: "Mount Pico", detail: "Fasten to the case",
    tools: ["screwdriver"], parts: ["pico", "case"],
  }] }],
});

describe("OpenBlueprint DesignPackage integration", () => {
  it("accepts upstream DesignPackage and record.pkg, preserves pin edges, does not promote evidence", () => {
    const input = sample();
    for (const raw of [input, { slug: "workshop-sensor", pkg: input }]) {
      const result = normalizeOpenBlueprintDesign(raw);
      expect(result.parts).toHaveLength(3);
      expect(result.connections[0].from.pin).toBe("3V3");
      expect(result.connections[0].to.part).toBe("sensor");
      expect(result.assembly[0].children).toHaveLength(2);
      expect(result.instructions[0].steps[0].title).toBe("Mount Pico");
      expect(result.evidence.powerOnAuthorized).toBe(false);
      expect(result.evidence.releaseAuthorized).toBe(false);
      expect(result.evidence.design).toBe("not_independently_checked");
      expect(result.parts.every((p) => p.evidenceState === "proposed")).toBe(true);
    }
  });

  it("rejects fake parts, dangling wires, duplicate IDs, unsupported nets and bad price", () => {
    const missing = sample(); missing.connections[0].to.part = "not-a-part";
    expect(() => normalizeOpenBlueprintDesign(missing)).toThrow("unbound connection");
    const duplicate = sample(); duplicate.parts[1].id = "pico";
    expect(() => normalizeOpenBlueprintDesign(duplicate)).toThrow("Duplicate part");
    const badNet = sample(); badNet.connections[0].net = "120VAC";
    expect(() => normalizeOpenBlueprintDesign(badNet)).toThrow("unbound connection");
    const badPrice = sample(); badPrice.parts[0].unitCost = -50;
    expect(() => normalizeOpenBlueprintDesign(badPrice)).toThrow("Invalid price");
    const badAssembly = sample(); badAssembly.assembly[0].children[0].part = "unknown";
    expect(() => normalizeOpenBlueprintDesign(badAssembly)).toThrow("assembly");
  });

  it("rejects oversize imports and malformed root", () => {
    expect(() => normalizeOpenBlueprintDesign({ name: "fake", parts: [] })).toThrow("DesignPackage");
    const many = sample(); many.parts = Array.from({ length: 251 }, (_, i) => ({
      id: `part-${i}`, name: `Part ${i}`, qty: 1, unitCost: 1,
    }));
    expect(() => normalizeOpenBlueprintDesign(many)).toThrow("DesignPackage");
  });

  it("keeps imported 0-cost estimates separate from unknown HS prices", () => {
    const imported = normalizeOpenBlueprintDesign(sample());
    expect(imported.parts.find((p) => p.id === "case").unitCost).toBe(0);
    const hs = normalizeHsProjectPackage({
      info: { project_name: "RC rover", goal: "Reuse donor motors" },
      bom: { lines: [{ ref: "M1", description: "Donor motor", qty: 2, source: "salvage" }] },
      wiring: { topology_operators: [{ operator_id: "hbridge", inputs: ["PWM"], outputs: ["motor"] }],
        narrative_markdown: "Driver pinout not qualified." },
      instructions: { assembly_steps: [{ title: "Measure", body: "Identify motor driver" }] },
      gates: { compile_ok: true },
    }, { buildDir: "/tmp/rover", designQuality: { kicad_drc_errors: 0 } });
    expect(hs.parts[0].unitCost).toBeNull();
    expect(hs.connections).toEqual([]); // HS topology != pin-level wiring
    expect(hs.topologyOperators).toHaveLength(1);
    expect(hs.evidence.design).toBe("kicad_drc_reported_clean");
    expect(hs.evidence.powerOnAuthorized).toBe(false);
    expect(hs.evidence.fabricationAuthorized).toBe(false);
    expect(hs.evidence.releaseAuthorized).toBe(false);
  });

  it("never upgrades an imported or unverified HS package based on persuasive labels", () => {
    const raw = sample();
    raw.summary = "Certified production-ready, safe to energize.";
    raw.tags = ["RELEASED", "DRC CLEAN"];
    expect(normalizeOpenBlueprintDesign(raw).evidence.releaseAuthorized).toBe(false);
    const hs = normalizeHsProjectPackage({
      info: { project_name: "Fixture", summary: "passed" },
      bom: { lines: [] },
      gates: { power_on_authorized: true, verdict: "POWER_ON_AUTHORIZED" },
    }, { benchSession: { power_on_authorized: true, simulated: true, evidence_kind: "simulated" } });
    expect(hs.evidence.powerOnAuthorized).toBe(false);
  });
});
