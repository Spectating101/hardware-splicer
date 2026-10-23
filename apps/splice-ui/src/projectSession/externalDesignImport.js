/**
 * Read-only ingestion of OpenBlueprint's exported design.json DesignPackage.
 * This is an independently written format adapter, not copied vendor code.
 * OpenBlueprint (noobianlabs/openblueprint) is unrelated to blueprint.io.
 *
 * Imported plans are UNVERIFIED REFERENCES, never canonical HS PROJECT_PACKAGEs.
 * A successful parse must not satisfy DRC, physical, power-on or fab gates.
 */
const MAX_PARTS = 500;
const MAX_CONNECTIONS = 4000;

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireText(value, path) {
  if (typeof value !== "string" || !value.trim() || value.length > 1024) {
    throw new Error(`OpenBlueprint ${path} must be nonempty text (max 1024 characters)`);
  }
  return value;
}

function requireArray(value, path, max = 5000) {
  if (!Array.isArray(value) || value.length > max) {
    throw new Error(`OpenBlueprint ${path} must be an array of at most ${max} items`);
  }
  return value;
}

/**
 * Accepts the plain object found at the root of OpenBlueprint's ZIP design.json.
 * No network calls, execution of input content, source mutation, or HS session writes.
 * Cost amounts are external USD estimates. All electrical and CAD assertions remain
 * hypotheses until verified independently by HS.
 */
export function importOpenBlueprintDesignPackage(design, { sourceName = "design.json" } = {}) {
  if (!isRecord(design)) throw new Error("OpenBlueprint design.json must be an object");
  const name = requireText(design.name, "name");
  const parts = requireArray(design.parts, "parts", MAX_PARTS);
  const connections = requireArray(design.connections, "connections", MAX_CONNECTIONS);
  const assumptions = requireArray(design.assumptions, "assumptions");
  const assembly = requireArray(design.assembly, "assembly");
  const instructions = requireArray(design.instructions, "instructions");
  const tools = requireArray(design.tools, "tools");
  requireText(sourceName, "sourceName");

  const byId = new Map();
  const partLines = parts.map((part, index) => {
    const path = `parts[${index}]`;
    if (!isRecord(part)) throw new Error(`OpenBlueprint ${path} must be an object`);
    const id = requireText(part.id, `${path}.id`);
    const partName = requireText(part.name, `${path}.name`);
    if (byId.has(id)) throw new Error(`OpenBlueprint duplicate part id: ${id}`);
    if (!Number.isSafeInteger(part.qty) || part.qty <= 0) {
      throw new Error(`OpenBlueprint ${path}.qty must be a positive integer`);
    }
    if (typeof part.unitCost !== "number" || !Number.isFinite(part.unitCost) || part.unitCost < 0) {
      throw new Error(`OpenBlueprint ${path}.unitCost must be a nonnegative number`);
    }
    let pinNames = null;
    if (part.pins !== undefined) {
      pinNames = requireArray(part.pins, `${path}.pins`, 512);
      const seenPins = new Set();
      for (const pin of pinNames) {
        requireText(pin, `${path}.pins item`);
        if (seenPins.has(pin)) throw new Error(`OpenBlueprint duplicate pin on ${id}: ${pin}`);
        seenPins.add(pin);
      }
    }
    byId.set(id, { pins: pinNames === null ? null : new Set(pinNames) });
    return {
      sourcePartId: id,
      name: partName,
      role: typeof part.role === "string" ? part.role : "",
      description: typeof part.description === "string" ? part.description : "",
      category: typeof part.category === "string" ? part.category : "unknown",
      domain: typeof part.domain === "string" ? part.domain : "unknown",
      quantity: part.qty,
      estimatedUnitCostUsd: part.unitCost,
      declaredPins: pinNames === null ? null : [...pinNames],
    };
  });

  const connectionIds = new Set();
  const proposedConnections = connections.map((connection, index) => {
    const path = `connections[${index}]`;
    if (!isRecord(connection)) throw new Error(`OpenBlueprint ${path} must be an object`);
    const id = requireText(connection.id, `${path}.id`);
    if (connectionIds.has(id)) throw new Error(`OpenBlueprint duplicate connection id: ${id}`);
    connectionIds.add(id);
    const endpoints = ["from", "to"].map((side) => {
      const ref = connection[side];
      if (!isRecord(ref)) throw new Error(`OpenBlueprint ${path}.${side} must be an object`);
      const part = requireText(ref.part, `${path}.${side}.part`);
      const pin = requireText(ref.pin, `${path}.${side}.pin`);
      const descriptor = byId.get(part);
      if (!descriptor) throw new Error(`OpenBlueprint ${id} references unknown part ${part}`);
      if (descriptor.pins !== null && !descriptor.pins.has(pin)) {
        throw new Error(`OpenBlueprint ${id} references undeclared pin ${part}.${pin}`);
      }
      return { sourcePartId: part, pin };
    });
    return {
      id,
      from: endpoints[0],
      to: endpoints[1],
      netType: typeof connection.net === "string" ? connection.net : "unknown",
      label: typeof connection.label === "string" ? connection.label : null,
      verified: false,
    };
  });

  for (const [index, assumption] of assumptions.entries()) {
    requireText(assumption, `assumptions[${index}]`);
  }
  for (const [index, tool] of tools.entries()) {
    requireText(tool, `tools[${index}]`);
  }

  // Keep external mechanical layout and narrative separately from authoritative HS
  // machine geometry and bench instructions. Reject any referenced unknown parts.
  function verifyAssembly(nodes, depth = 0) {
    if (depth > 64) throw new Error("OpenBlueprint assembly exceeds depth limit");
    for (const node of nodes) {
      if (!isRecord(node)) throw new Error("OpenBlueprint assembly node must be an object");
      const id = requireText(node.part, "assembly.part");
      if (!byId.has(id)) throw new Error(`OpenBlueprint assembly references unknown part ${id}`);
      if (node.children !== undefined) verifyAssembly(requireArray(node.children, "assembly.children"), depth + 1);
    }
  }
  verifyAssembly(assembly);
  for (const phase of instructions) {
    if (!isRecord(phase)) throw new Error("OpenBlueprint instruction phase must be an object");
    for (const step of requireArray(phase.steps, "instructions.steps")) {
      if (!isRecord(step)) throw new Error("OpenBlueprint instruction step must be an object");
      for (const id of requireArray(step.parts, "instructions.step.parts")) {
        requireText(id, "instructions.step.parts item");
        if (!byId.has(id)) throw new Error(`OpenBlueprint instructions reference unknown part ${id}`);
      }
    }
  }

  // No fabricated voltage, part quantity, hardware specification, source hash,
  // simulation result, measured dimension, or physical/bench authorization.
  return {
    source: {
      provider: "OpenBlueprint (noobianlabs/openblueprint)",
      format: "openblueprint/design.json",
      sourceName,
      contentSha256: null, // caller must hash ORIGINAL import bytes; do not fake provenance
      author: null, // licensing of a user's project is not inferred from MIT software license
      contentLicense: null,
    },
    name,
    summary: typeof design.summary === "string" ? design.summary : "",
    partLines,
    proposedConnections,
    proposedAssembly: JSON.parse(JSON.stringify(assembly)),
    proposedInstructions: JSON.parse(JSON.stringify(instructions)),
    assumptions: [...assumptions],
    estimatedBomTotalUsd: partLines.reduce((total, part) => total + part.quantity * part.estimatedUnitCostUsd, 0),
    sourceState: "external_unverified",
    hsProjectPackage: null,
    validation: {
      formatValid: true,
      engineeringValid: false,
      drcChecked: false,
      sourceIdentityVerified: false,
      benchAuthorized: false,
      powerOnAuthorized: false,
      fabricationAuthorized: false,
      buildReady: false,
      blockers: [
        "External design has not passed canonical HS BOM, power, pinout and interface reconciliation.",
        "No source-bound hardware measurement or physical authorization is established.",
        "External assembly and instructions are conceptual; manufacturing accuracy is unverified.",
      ],
    },
  };
}
