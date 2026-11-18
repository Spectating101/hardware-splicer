export const BASIS_LABELS = {
  custom: "CAD part",
  vendor_step: "vendor model",
  envelope: "envelope",
  proxy: "proxy",
  unknown: "unknown geometry",
};

export const DIFF_LABELS = {
  changed: "geometry changed",
  added: "added",
  removed: "removed · rev 7",
  unchanged: "unchanged",
};

export const TOUR = [
  { label: "Display stack", partId: "display", target: [155, 208, 50], angle: 18 },
  { label: "Cable (DSI)", interfaceId: "display-ribbon", angle: -5 },
  { label: "Changed parts", diff: "changed", angle: 24 },
];

export const VALIDATION_LABEL = "No physical validation performed";

export function classifyPart(part, delta, mode) {
  const basis = Object.hasOwn(BASIS_LABELS, part.geometry_basis) ? part.geometry_basis : "unknown";
  const diff = mode === "compare" ? delta : undefined;
  const outline = diff === "removed" || basis !== "custom" && basis !== "vendor_step";
  return { basis, diff, outline, dimmed: diff === "unchanged" };
}

// Revision-qualified keys distinguish the two displays, which share a part_id.
export function indexFielddeck(scenes) {
  const byKey = new Map();
  const byNode = new Map();
  const byPart = new Map();
  const { nodes = [] } = scenes["5"]?.revision_diff ?? {};
  const diff = new Map(nodes.map((row) => [JSON.stringify([row.node_name, row.occurrence]), row.status]));
  for (const [revision, scene] of Object.entries(scenes)) {
    if (!scene) continue;
    const occurrences = new Map();
    for (const part of scene.parts) {
      const name = part.node_name;
      const occurrence = (occurrences.get(name) ?? 0) + 1;
      occurrences.set(name, occurrence);
      const key = `${revision}:part:${part.part_id}`;
      const row = {
        key, revision, part, delta: diff.get(JSON.stringify([name, occurrence])),
      };
      byKey.set(key, row);
      const nodesForRevision = byNode.get(revision) ?? new Map();
      const matches = nodesForRevision.get(name) ?? [];
      matches.push(row);
      nodesForRevision.set(name, matches);
      byNode.set(revision, nodesForRevision);
      byPart.set(`${revision}:${part.part_id}`, row);
    }
    for (const link of scene.interfaces) {
      const key = `${revision}:link:${link.interface_id}`;
      byKey.set(key, { key, revision, link });
    }
  }
  return { byKey, byNode, byPart };
}

export function rowForNode(index, revision, exactName, nodeIndex) {
  const matches = index.byNode.get(revision)?.get(exactName);
  if (matches?.length === 1) return matches[0];
  return matches?.find(({ part }) => part.node_index === nodeIndex);
}

export function rowsForMode(index, mode) {
  return [...index.byKey.values()].filter((row) =>
    mode === "compare"
      ? row.revision === "5" || row.part && row.delta === "removed"
      : row.revision === mode,
  );
}

export function selectedPartKeys(index, row) {
  if (!row) return [];
  if (row.part) return [row.key];
  return [row.link.from_part_id, row.link.to_part_id]
    .map((id) => index.byPart.get(`${row.revision}:${id}`)?.key)
    .filter(Boolean);
}

function evidenceText(value) {
  if (value == null) return "unknown";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function evidenceCells(row) {
  return [row.field, row.state === "unknown" ? "unknown" : evidenceText(row.value), row.state, evidenceText(row.source)];
}
