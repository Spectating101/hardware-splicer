/**
 * Read-only interoperability with OpenBlueprint's MIT DesignPackage shape.
 *
 * Upstream: https://github.com/noobianlabs/openblueprint
 * Contract: src/lib/design/schema.ts (OpenBlueprint contributors, MIT).
 * This is a compatibility adapter, NOT an engineering approval or a fork of
 * OpenBlueprint's keyless/Claude generation engine.
 */
const CATEGORIES = new Set(["mcu", "sensor", "actuator", "power", "comms", "display",
  "module", "enclosure", "print3d", "misc"]);
const DOMAINS = new Set(["electrical", "mechanical"]);
const NETS = new Set(["data", "power", "ground"]);
const MAX_PARTS = 250;
const MAX_CONNECTIONS = 750;

function text(value, max = 500) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

function array(value, limit) {
  return Array.isArray(value) ? value.slice(0, limit) : [];
}

function safeCost(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

function normalizePart(raw, i, source) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error(`Part ${i + 1} is not an object`);
  const id = text(raw.id, 120);
  if (!id) throw new Error(`Part ${i + 1} is missing its ID`);
  const category = CATEGORIES.has(raw.category) ? raw.category : "misc";
  const domain = DOMAINS.has(raw.domain) ? raw.domain :
    (category === "enclosure" || category === "print3d" ? "mechanical" : "electrical");
  const qty = raw.qty === undefined ? 1 : Number(raw.qty);
  if (!Number.isInteger(qty) || qty < 1 || qty > 10000) throw new Error(`Invalid quantity for ${id}`);
  const unitCost = safeCost(raw.unitCost);
  if (raw.unitCost != null && unitCost === null) throw new Error(`Invalid price for ${id}`);
  return {
    id, name: text(raw.name, 200) || id, role: text(raw.role, 200),
    description: text(raw.description, 1000), category, domain, qty, unitCost,
    pins: array(raw.pins, 100).map((p) => text(p, 100)).filter(Boolean),
    source: text(raw.source, 120) || source,
    evidenceState: "proposed",
  };
}

function checkAssembly(roots, partIds) {
  let count = 0;
  function check(node, depth) {
    count += 1;
    if (count > 400 || depth > 16 || !node || typeof node !== "object" ||
        !partIds.has(node.part)) throw new Error("Invalid or unbound assembly tree");
    return { part: node.part, children: array(node.children, 100).map((c) => check(c, depth + 1)) };
  }
  return array(roots, 250).map((root) => check(root, 0));
}

function normalizeConnections(rows, partIds) {
  if (!Array.isArray(rows) || rows.length > MAX_CONNECTIONS) throw new Error("Invalid or oversized connections");
  const seen = new Set();
  return rows.map((row, index) => {
    const id = text(row?.id, 120) || `wire-${index}`;
    const from = { part: text(row?.from?.part, 120), pin: text(row?.from?.pin, 120) };
    const to = { part: text(row?.to?.part, 120), pin: text(row?.to?.pin, 120) };
    if (seen.has(id) || !partIds.has(from.part) || !partIds.has(to.part) ||
        !from.pin || !to.pin || !NETS.has(row.net)) {
      throw new Error(`Invalid or unbound connection ${id}`);
    }
    seen.add(id);
    return { id, from, to, net: row.net, label: text(row.label, 120) };
  });
}

function normalizeInstructions(phases) {
  if (!Array.isArray(phases) || phases.length > 60) throw new Error("Invalid instructions");
  return phases.map((phase, i) => ({
    id: text(phase?.id, 120) || `phase-${i}`,
    title: text(phase?.title, 250) || `Phase ${i + 1}`,
    steps: array(phase?.steps, 100).map((step, j) => ({
      id: text(step?.id, 120) || `${i + 1}.${j + 1}`,
      title: text(step?.title, 250),
      detail: text(step?.detail, 2000),
      tools: array(step?.tools, 100).map((x) => text(x, 120)),
      parts: array(step?.parts, 100).map((x) => text(x, 120)),
    })),
  }));
}

export function normalizeOpenBlueprintDesign(input) {
  const raw = input?.pkg || input;
  if (!raw || typeof raw !== "object" || Array.isArray(raw) ||
      !text(raw.name) || !Array.isArray(raw.parts) || !Array.isArray(raw.connections) ||
      !Array.isArray(raw.assembly) || !Array.isArray(raw.instructions) ||
      raw.parts.length > MAX_PARTS) {
    throw new Error("Expected an OpenBlueprint DesignPackage with name, parts, connections, assembly and instructions");
  }
  const parts = raw.parts.map((p, i) => normalizePart(p, i, "openblueprint"));
  const partIds = new Set(parts.map((p) => p.id));
  if (partIds.size !== parts.length) throw new Error("Duplicate part ID");
  const connections = normalizeConnections(raw.connections, partIds);
  const assembly = checkAssembly(raw.assembly, partIds);
  const instructions = normalizeInstructions(raw.instructions);
  for (const phase of instructions) {
    for (const step of phase.steps) {
      if (step.parts.some((id) => !partIds.has(id))) {
        throw new Error(`Instruction ${step.id} references a missing part`);
      }
    }
  }
  return {
    schema: "hardware_splicer.blueprint_view.v1",
    source: "openblueprint_import",
    name: text(raw.name, 200),
    summary: text(raw.summary, 3000),
    tags: array(raw.tags, 40).map((x) => text(x, 100)),
    parts, connections, assembly, instructions,
    tools: array(raw.tools, 100).map((x) => text(x, 120)),
    assumptions: array(raw.assumptions, 100).map((x) => text(x, 500)),
    topologyOperators: [],
    wiringNarrative: "",
    mechanical: { status: "schematic_assembly_only", cadAvailable: false },
    firmware: null,
    evidence: {
      design: "not_independently_checked", electrical: "not_independently_checked",
      physical: "not_measured", powerOnAuthorized: false,
      fabricationAuthorized: false, releaseAuthorized: false,
      provenance: "imported_user_supplied_design_not_approved",
    },
  };
}

/**
 * Adapt an existing HS PROJECT_PACKAGE without fabricating pin-level wiring,
 * geometry, prices, supplier listings or physical evidence.
 */
export function normalizeHsProjectPackage(pkg, session = {}) {
  if (!pkg || typeof pkg !== "object" || !pkg.info || !pkg.bom) {
    throw new Error("Expected a Hardware Splicer PROJECT_PACKAGE");
  }
  const lines = array(pkg.bom.lines, MAX_PARTS);
  if ((pkg.bom.lines || []).length > MAX_PARTS) throw new Error("Oversized HS BOM");
  const seen = new Set();
  const parts = lines.map((line, i) => {
    const original = text(line.ref || line.module_id, 120) || `part-${i + 1}`;
    let id = original;
    let suffix = 2;
    while (seen.has(id)) id = `${original}-${suffix++}`;
    seen.add(id);
    const rawPrice = line.estimated_unit_usd ?? line.unit_price_usd ?? line.price_usd;
    const parsedPrice = rawPrice == null ? null : Number(rawPrice);
    return normalizePart({
      id, name: line.description || line.module_id || line.ref || id,
      role: line.source || "BOM entry", description: line.description || "",
      category: "module", domain: "electrical",
      qty: line.qty ?? 1,
      unitCost: Number.isFinite(parsedPrice) && parsedPrice >= 0 ? parsedPrice : undefined,
      source: line.source || "hs_bom",
    }, i, "hs_bom");
  });
  const steps = array(pkg.instructions?.assembly_steps, 100).map((s, i) => ({
    id: String(i + 1), title: text(s?.title || `Step ${i + 1}`, 250),
    detail: typeof s === "string" ? text(s, 2000) : text(s?.body, 2000),
    tools: [], parts: [],
  }));
  const designQuality = session.designQuality || session.displayResult?.design_quality || {};
  const drc = designQuality.kicad_drc_errors ?? pkg.gates?.kicad_drc_errors;
  const drcClean = drc === 0 && (session.buildDir || pkg.build_dir);
  const bench = session.benchSession || session.displayResult?.bench_session || {};
  const physical = bench.evidence_kind === "physical" && bench.simulated !== true;
  return {
    schema: "hardware_splicer.blueprint_view.v1",
    source: "hardware_splicer_project_package",
    name: text(pkg.info.project_name || session.projectName, 200) || "HS project",
    summary: text(pkg.info.summary || pkg.info.goal || session.goal, 3000),
    tags: [text(pkg.info.archetype, 100)].filter(Boolean),
    parts,
    // The HS PROJECT_PACKAGE has topology operators and a wiring narrative,
    // but does NOT guarantee pin-level Connection records.
    connections: [],
    assembly: [],
    instructions: steps.length ? [{ id: "hs-assembly", title: "Build package steps", steps }] : [],
    tools: [],
    assumptions: array(pkg.info.assumptions, 100).map((x) => text(x, 500)),
    topologyOperators: array(pkg.wiring?.topology_operators, 200),
    wiringNarrative: text(pkg.wiring?.narrative_markdown, 15000),
    mechanical: {
      status: text(pkg.mechanism_pack?.status || pkg.mech?.physical_assembly?.status, 150) ||
        "geometry_not_verified",
      cadAvailable: false,
      previewPath: text(pkg.mech?.preview_path, 300),
    },
    firmware: pkg.firmware_scaffold ? {
      filename: text(pkg.firmware_scaffold.filename, 150),
      source: text(pkg.firmware_scaffold.source, 10000),
      compileVerified: false,
    } : null,
    evidence: {
      design: drcClean ? "kicad_drc_reported_clean" : "unknown_or_unchecked",
      electrical: drcClean ? "kicad_drc_reported_clean_not_physical" : "unknown_or_unchecked",
      physical: physical ? "physical_capture_claim_present_review_required" : "not_measured",
      powerOnAuthorized: physical && bench.power_on_authorized === true,
      fabricationAuthorized: false,
      releaseAuthorized: false,
      provenance: "hardware_splicer_package_read_only",
      revision: session.snapshotRevision || null,
      buildDir: session.buildDir || pkg.build_dir || null,
    },
  };
}
