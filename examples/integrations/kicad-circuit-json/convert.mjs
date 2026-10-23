/**
 * Actual KiCad-to-Circuit-JSON source interchange probe.
 * Uses upstream open-source tooling; NEVER treats conversion as proof of
 * complete topology or fabrication correctness.
 *
 * npm install && npm run convert -- /absolute/project.kicad_sch /tmp/output.json
 */
import { KicadToCircuitJsonConverter } from "kicad-to-circuit-json";
import { readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";

const source = process.argv[2];
if (!source || !/\.kicad_(sch|pcb)$/.test(source)) {
  throw Error("Provide a user-owned .kicad_sch or .kicad_pcb path");
}
const target = process.argv[3] || resolve("external-circuit.json");
const converter = new KicadToCircuitJsonConverter();
converter.addFile(basename(source), readFileSync(source, "utf8"));
await converter.runUntilFinished();
const documents = converter.getOutput();
if (!Array.isArray(documents) || !documents.length) {
  throw Error("Upstream converter returned no Circuit JSON documents");
}
writeFileSync(target, JSON.stringify(documents, null, 2) + "\n");
const counts = Object.fromEntries([...new Set(documents.map((item) => item.type))]
  .map((type) => [type, documents.filter((item) => item.type === type).length]));
console.log(JSON.stringify({
  source, target, records: documents.length, counts,
  warnings: converter.getWarnings(),
  claim: "Converted source, NOT verified HS connectivity, firmware or physical design",
}, null, 2));
