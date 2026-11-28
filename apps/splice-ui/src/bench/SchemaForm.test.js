import { describe, expect, it } from "vitest";
import { argsFromValues, fieldKind, valuesFromArgs } from "./SchemaForm.jsx";

const schema = {
  type: "object",
  properties: {
    pcb: { type: "string" },
    net_currents_a: { type: "object" },
    max_rise_c: { type: "number" },
    dry: { type: "boolean" },
  },
  required: ["pcb", "net_currents_a"],
};

describe("workbench schema form", () => {
  it("reads each field by its schema type", () => {
    expect(fieldKind({ type: "integer" })).toBe("number");
    expect(fieldKind({})).toBe("json");
    expect(fieldKind({ enum: ["a"] })).toBe("enum");
  });

  it("turns typed text into arguments and leaves blank optional fields out", () => {
    const { args, errors } = argsFromValues(schema, { pcb: "b.kicad_pcb", net_currents_a: '{"/VIN": 5}', max_rise_c: " " });
    expect(errors).toEqual({});
    expect(args).toEqual({ pcb: "b.kicad_pcb", net_currents_a: { "/VIN": 5 } });
  });

  it("names the field that cannot be read instead of sending it", () => {
    const { errors } = argsFromValues(schema, { net_currents_a: "{5", max_rise_c: "hot" });
    expect(errors).toEqual({ pcb: "Required", net_currents_a: "Not valid JSON", max_rise_c: "Enter a number" });
  });

  it("round-trips an example through the form", () => {
    const example = { pcb: "b.kicad_pcb", net_currents_a: { "/VIN": 5 }, max_rise_c: 20, dry: true };
    expect(argsFromValues(schema, valuesFromArgs(schema, example)).args).toEqual(example);
  });
});

import { score } from "./panels.jsx";

describe("workbench palette ranking", () => {
  it("puts a name's initials ahead of letters scattered through a hint", () => {
    expect(score("krt", "KiCadRoutingTools", "Routing · MIT")).toBeGreaterThan(score("krt", "04 Read-back parity", "KiCad ERC and DRC (kicad-cli)"));
    expect(score("trace", "Trace current", "hs_trace_current")).toBeGreaterThan(score("trace", "12 Track current", "HS"));
    expect(score("zzz", "Design", "HS")).toBe(0);
  });
});
