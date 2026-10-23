#!/usr/bin/env node
/**
 * Independent Wokwi -> HS artifact-coverage challenge.
 * Usage: node examples/integrations/wokwi/challenge.mjs diagram.json [PROJECT_PACKAGE.json]
 *
 * No Wokwi API/token or physical device is accessed. Does not invoke Wokwi
 * simulation or assert engineering parity. Fail only when source content is
 * LOST or invalid (coverage shortfalls remain visible in JSON result).
 */
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import {
  parseWokwiDiagramArtifact, compareWokwiCandidateToHsBom,
} from "../../../apps/splice-ui/src/components/wokwiInterop.js";

const original = process.argv[2];
if (!original) {
  process.stderr.write("Usage: node challenge.mjs /path/to/diagram.json [/path/to/PROJECT_PACKAGE.json]\n");
  process.exit(2);
}
try {
  const bytes = readFileSync(resolve(original));
  const raw = JSON.parse(bytes.toString("utf8"));
  const parsed = parseWokwiDiagramArtifact(bytes.toString("utf8"));
  const sourceComplete = parsed.nodes.length === raw.parts.length &&
    parsed.connections.length === raw.connections.length;
  if (!sourceComplete) throw new Error("Source information lost during provider conversion.");

  let comparison = null;
  if (process.argv[3]) {
    const pkg = JSON.parse(readFileSync(resolve(process.argv[3]),"utf8"));
    comparison = compareWokwiCandidateToHsBom(parsed, pkg.bom?.lines);
  }
  const output = {
    benchmark: "wokwi_hs_portability_v1",
    input_sha256: createHash("sha256").update(bytes).digest("hex"),
    source: {
      part_count: raw.parts.length,
      connection_count: raw.connections.length,
      editor: raw.editor ?? "unknown",
    },
    hs: {
      preserved_part_count: parsed.nodes.length,
      preserved_connection_count: parsed.connections.length,
      mapped_part_families: parsed.mapped_part_count,
      mapped_pin_connections: parsed.mapped_connection_count,
      unmatched_part_ids: parsed.unmapped_part_ids,
      unmatched_connections: parsed.unmapped_connections,
      draft_import_eligible: parsed.status === "family_mapping_only",
      source_authority: parsed.authority,
      physical_approval: false,
      simulation_executed: false,
      status: parsed.status,
    },
    compared_to_hs_bom: comparison,
  };
  process.stdout.write(JSON.stringify(output, null, 2)+"\n");
} catch (err) {
  process.stderr.write(`Provider challenge failed: ${err.message}\n`);
  process.exitCode = 1;
}
