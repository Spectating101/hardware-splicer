/**
 * Export upstream Circuit JSON together with its converter-runtime-native
 * KiCad symbol UUID → schematic_component_id mapping.
 *
 * IMPORTANT: This reads the upstream converter's internal ctx map, which
 * already exists in v0.0.144. It does NOT derive identity from positions
 * or write non-standard properties into Circuit JSON. Strict companion
 * provenance must be independently audited against native .kicad_sch.
 *
 * Usage: node convert_with_provenance.mjs schematic.kicad_sch out.json sidecar.json
 */
import { KicadToCircuitJsonConverter } from "kicad-to-circuit-json";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";

const [source, out, provenanceOut] = process.argv.slice(2);
if (!source?.endsWith(".kicad_sch") || !out || !provenanceOut) {
  throw Error("Usage: node convert_with_provenance.mjs INPUT.kicad_sch OUT.json PROVENANCE.json");
}
const original = readFileSync(source, "utf8");
const converter = new KicadToCircuitJsonConverter();
converter.addFile(basename(source), original);
converter.runUntilFinished();
const documents = converter.getOutput();
const originalMap = converter.ctx?.symbolUuidToComponentId;
const symbols = converter.ctx?.kicadSch?.symbols;
if (!(originalMap instanceof Map) || !Array.isArray(symbols) || !symbols.length) {
  throw Error("Upstream converter did not expose a native source-symbol UUID mapping");
}
const schematicById = new Map(documents.filter(x => x.type === "schematic_component")
  .map(x => [x.schematic_component_id, x]));
const sourceById = new Map(documents.filter(x => x.type === "source_component")
  .map(x => [x.source_component_id, x]));
const allPorts = documents.filter(x => x.type === "source_port");
if (new Set(schematicById.keys()).size !== schematicById.size ||
    originalMap.size !== symbols.length ||
    schematicById.size !== symbols.length) {
  throw Error("Incomplete/ambiguous UUID or schematic component mapping");
}
const rows = [];
const refSeen = new Set();
const idSeen = new Set();
for (const symbol of symbols) {
  const uuid = symbol.uuid;
  const id = originalMap.get(uuid);
  const visual = schematicById.get(id);
  if (!uuid || !visual || idSeen.has(id)) {
    throw Error("Native UUID failed to resolve to unique actual converter schematic component");
  }
  idSeen.add(id);
  const cid = visual.source_component_id;
  if (!sourceById.has(cid)) throw Error("Converted visual component missing source_component");
  const propertyRef = symbol.properties?.filter(x => x.key === "Reference") ?? [];
  if (propertyRef.length !== 1 || !propertyRef[0].value) {
    throw Error("Native source component lacks unique reference property");
  }
  const projectPaths = (symbol.instances?.projects ?? []).flatMap(project =>
    (project.paths ?? []).map(path => ({
      project: project.name,
      sheet_uuid_path: path.value,
      ref: path.reference ?? "",
      unit: path.unit ?? null,
    }))
  );
  if (projectPaths.length !== 1 || !projectPaths[0].sheet_uuid_path ||
      projectPaths[0].ref !== propertyRef[0].value) {
    // Multiple hierarchical instantiations require distinct per-instance
    // converter records. This converter currently does not implement them.
    throw Error("Missing/ambiguous native KiCad sheet-instance path or reference");
  }
  const path = projectPaths[0];
  if (refSeen.has(path.ref)) throw Error("Duplicate native reference in converter output");
  refSeen.add(path.ref);
  const pinNumbers = allPorts.filter(x => x.source_component_id === cid)
    .map(x => x.pin_number != null ? String(x.pin_number) : null);
  if (pinNumbers.some(p => !p) || new Set(pinNumbers).size !== pinNumbers.length) {
    throw Error("Missing/duplicate numeric pin IDs in source component");
  }
  rows.push({
    native_symbol_uuid: uuid,
    native_reference: path.ref,
    native_project: path.project,
    native_sheet_uuid_path: path.sheet_uuid_path,
    native_unit: path.unit,
    native_library_id: symbol.libraryId ?? "",
    native_position_mm: { x: symbol.at?.x, y: symbol.at?.y },
    schematic_component_id: id,
    source_component_id: cid,
    source_pin_numbers: pinNumbers.sort(),
  });
}
if (rows.length !== symbols.length ||
    new Set(rows.map(x => x.native_symbol_uuid)).size !== rows.length ||
    new Set(rows.map(x => x.native_reference)).size !== rows.length ||
    rows.length !== sourceById.size) {
  throw Error("Native UUID map does not bijectively cover converter output");
}
const documentsText = JSON.stringify(documents, null, 2) + "\n";
const sha = raw => createHash("sha256").update(raw).digest("hex");
const sidecar = {
  schema_version: "hardware_splicer.kicad_upstream_runtime_provenance.v1",
  upstream_converter_version: "0.0.144",
  capture: "upstream_converter_ctx_symbolUuidToComponentId",
  source_sha256: sha(original),
  converter_output_sha256: sha(documentsText),
  converter_component_count: sourceById.size,
  converter_schematic_component_count: schematicById.size,
  native_uuid_mapped_count: rows.length,
  original_converter_output_modified: false,
  source_wire_connectivity_authenticated: false,
  sheet_instance_assumption: "exactly_one_native_instance_path_per_symbol",
  records: rows.sort((a,b) => a.native_reference.localeCompare(b.native_reference)),
};
writeFileSync(out, documentsText);
writeFileSync(provenanceOut, JSON.stringify(sidecar, null, 2) + "\n");
console.log(JSON.stringify({
  original_converter_docs: documents.length,
  converter_symbols: schematicById.size,
  native_uuid_mapped: rows.length,
  sidecar: provenanceOut,
  original_converter_output_modified: false,
  manufacturing_authorized: false,
}, null, 2));
