/**
 * Live upstream tscircuit -> Circuit JSON input for HS.
 * Run: npm install && npm run generate
 * Output is a DRAFT proposal, not a verified fabricated board.
 */
import React from "react";
import { RootCircuit } from "@tscircuit/core";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const circuit = new RootCircuit();
circuit.add(React.createElement("board", { width: "25mm", height: "25mm", pcbDisabled: true },
  React.createElement("resistor", { name: "R1", resistance: "1k", footprint: "0402" }),
  React.createElement("capacitor", { name: "C1", capacitance: "1uF", footprint: "0402" }),
  React.createElement("resistor", { name: "R2", resistance: "10k", footprint: "0402" }),
  React.createElement("capacitor", { name: "C2", capacitance: "100nF", footprint: "0402" }),
  React.createElement("trace", { from: ".R1 > .pin1", to: "net.VCC" }),
  React.createElement("trace", { from: ".R1 > .pin2", to: ".C1 > .pin1" }),
  React.createElement("trace", { from: ".C1 > .pin2", to: "net.GND" }),
  React.createElement("trace", { from: ".R2 > .pin1", to: "net.VCC" }),
  React.createElement("trace", { from: ".R2 > .pin2", to: ".C2 > .pin1" }),
  React.createElement("trace", { from: ".C2 > .pin2", to: "net.GND" }),
));
await circuit.renderUntilSettled();
const documents = circuit.getCircuitJson();
const root = dirname(fileURLToPath(import.meta.url));
const out = process.argv[2] || join(root, "generated-circuit.json");
writeFileSync(out, JSON.stringify(documents, null, 2) + "\n");
const counts = Object.fromEntries([...new Set(documents.map((doc) => doc.type))]
  .map((type) => [type, documents.filter((doc) => doc.type === type).length]));
console.log(JSON.stringify({
  source: "live-tscircuit-core",
  output: out,
  record_count: documents.length,
  source_components: counts.source_component || 0,
  source_ports: counts.source_port || 0,
  source_traces: counts.source_trace || 0,
  upstream_warnings: Object.entries(counts).filter(([k]) => k.endsWith("_warning")),
  upstream_errors: Object.entries(counts).filter(([k]) => k.endsWith("_error")),
}, null, 2));
