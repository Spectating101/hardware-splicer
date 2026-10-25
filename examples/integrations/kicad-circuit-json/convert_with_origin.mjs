/**
 * Run ONLY an instrumented upstream source checkout installed as a local package.
 * The unmodified npm 0.0.144 distribution does not expose this method.
 *
 * Usage: node convert_with_origin.mjs source.kicad_sch out.json origin.json
 */
import { KicadToCircuitJsonConverter } from "kicad-to-circuit-json"
import { readFileSync, writeFileSync } from "node:fs"
import { basename } from "node:path"
import { createHash } from "node:crypto"

const [sourcePath, outputPath, originPath] = process.argv.slice(2)
if (!sourcePath?.endsWith(".kicad_sch") || !outputPath || !originPath) {
  throw new Error("Usage: node convert_with_origin.mjs file.kicad_sch circuit.json origin.json")
}
const source = readFileSync(sourcePath, "utf8")
const converter = new KicadToCircuitJsonConverter()
if (typeof converter.getNativeOriginSidecar !== "function") {
  throw new Error("Unpatched converter: parser-origin provenance is unavailable")
}
converter.addFile(basename(sourcePath), source)
await converter.runUntilFinished()
const circuit = converter.getOutput()
const sidecar = converter.getNativeOriginSidecar()
const components = circuit.filter((x) => x.type === "source_component")
const ports = circuit.filter((x) => x.type === "source_port")
if (!Array.isArray(sidecar.entries) || sidecar.entries.length !== components.length) {
  throw new Error("Parser-sidecar component count disagrees with Circuit JSON")
}
const componentIds = new Set(components.map((x) => x.source_component_id))
const portIds = new Set(ports.map((x) => x.source_port_id))
const recorded = new Set()
for (const entry of sidecar.entries) {
  if (!entry.native_kicad_symbol_uuid || !componentIds.has(entry.source_component_id) ||
      !entry.schematic_component_id || !Array.isArray(entry.source_port_ids)) {
    throw new Error("Incomplete parser-stage origin record")
  }
  if (recorded.has(entry.source_component_id)) throw new Error("Repeated converter component origin")
  recorded.add(entry.source_component_id)
  for (const id of entry.source_port_ids) {
    if (!portIds.has(id)) throw new Error("Dangling parser-origin source port ID")
  }
}
const emittedPortIds = sidecar.entries.flatMap((entry) => entry.source_port_ids)
if (emittedPortIds.length !== new Set(emittedPortIds).size ||
    emittedPortIds.length !== ports.length) {
  throw new Error("Parser-origin source port coverage mismatch")
}
sidecar.original_source_sha256 = createHash("sha256").update(source).digest("hex")
sidecar.circuit_json_sha256 = createHash("sha256")
  .update(JSON.stringify(circuit)).digest("hex")
sidecar.native_sheet_paths_authenticated = false
sidecar.authoritative_native_provenance = false
writeFileSync(outputPath, JSON.stringify(circuit, null, 2) + "\n")
writeFileSync(originPath, JSON.stringify(sidecar, null, 2) + "\n")
console.log(JSON.stringify({ components: components.length, ports: ports.length,
  captured: sidecar.entries.length, native_sheet_paths_authenticated: false,
  authoritative_native_provenance: false }, null, 2))
