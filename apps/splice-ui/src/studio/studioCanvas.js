/** Canvas state ↔ compose job payload (pin-level React Flow). */

export function buildComposePayload(nodes, edges, { phrase = "", allowLlmFirst = false, drcFixup = null } = {}) {
  const canvasNodes = nodes
    .filter((n) => n.type === "module" && n.data?.moduleId)
    .map((n) => ({ id: n.id, moduleId: n.data.moduleId }));

  const canvasWires = edges
    .filter((e) => e.source && e.target && e.sourceHandle && e.targetHandle)
    .map((e) => ({
      from: { nodeId: e.source, pinId: e.sourceHandle },
      to: { nodeId: e.target, pinId: e.targetHandle },
    }));

  const payload = {
    export_gerber: false,
    material_mode: "scratch",
    allow_llm_first: allowLlmFirst,
    constraints: { runtime_min: 20, battery_voltage_v: 7.4 },
  };

  if (drcFixup && Object.keys(drcFixup).length) {
    payload.drc_fixup = drcFixup;
  }

  if (phrase.trim()) {
    payload.phrase = phrase.trim();
  }

  if (canvasNodes.length >= 2) {
    payload.canvas_nodes = canvasNodes;
    if (canvasWires.length) {
      payload.canvas_wires = canvasWires;
    }
    return payload;
  }

  if (phrase.trim()) {
    return payload;
  }

  return null;
}

export function nextNodeId(existing) {
  let i = existing.length + 1;
  const ids = new Set(existing.map((n) => n.id));
  while (ids.has(`m${i}`)) i += 1;
  return `m${i}`;
}

export function createModuleNode(moduleId, { id, position, spec }) {
  return {
    id,
    type: "module",
    position,
    data: { moduleId, spec },
  };
}

export function indexModules(modules) {
  const map = new Map();
  for (const row of modules || []) {
    if (row?.id) map.set(row.id, row);
  }
  return map;
}

export function groupByCategory(modules) {
  const groups = new Map();
  for (const row of modules || []) {
    const cat = row.category || "other";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(row);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}
