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
  { label: "Display stack", partId: "display", angle: 18 },
  { label: "Cable (DSI)", interfaceId: "display-ribbon", angle: -5 },
  { label: "Changed parts", diff: "changed", angle: 24 },
];

export const VALIDATION_LABEL = "No physical validation performed";
export const DEFAULT_EXPLODE = 0.55;

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

const precision = new Intl.NumberFormat("en", { useGrouping: false, maximumFractionDigits: 2 });
const units = { mm: "mm", mm3: "mm³", w: "W" };
const repo = "https://github.com/Spectating101/hardware-splicer/blob/main/";
const fielddeckProject = "projects/cyberdeck-real-trial-20261020/";

function formatNumber(value) {
  const result = precision.format(value);
  return result === "-0" ? "0" : result;
}

export function formatEvidenceValue({ field, value, state }) {
  if (state === "unknown" || value == null) return "unknown";
  const unit = units[field.match(/_(mm3|mm|w)$/)?.[1]];
  const suffix = unit ? ` ${unit}` : "";
  if (typeof value === "number") return formatNumber(value) + suffix;
  if (Array.isArray(value) && value.every((item) => typeof item === "number")) {
    if (field.endsWith("_bounds_mm") && value.length === 6) {
      return ["X", "Y", "Z"].map((axis, i) =>
        `${axis} ${formatNumber(value[i])}→${formatNumber(value[i + 3])}`,
      ).join(" · ") + suffix;
    }
    return value.map(formatNumber).join(" × ") + suffix;
  }
  return typeof value === "object"
    ? JSON.stringify(value, (_key, item) => typeof item === "number" ? Number(formatNumber(item)) : item)
    : String(value);
}

export function formatEvidenceSource(source) {
  if (!source || source === "unknown") return { label: "unknown" };
  if (/^https?:\/\//i.test(source) && URL.canParse(source)) {
    const { hostname } = new URL(source);
    return { label: hostname.replace(/^www\./, ""), href: source };
  }
  const path = source.replace(/^\.\//, "");
  const label = path.split("/").at(-1);
  const prefix = /^(digital_v1|display_swap)\//.test(path) ? fielddeckProject : "";
  return { label, href: repo + prefix + path };
}

export function evidenceCells(row) {
  return [row.field, formatEvidenceValue(row), row.state, formatEvidenceSource(row.source)];
}
