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
export const DEFAULT_EXPLODE = 0.6;
export const FIELDDECK_NARROW = "(width < 700px)";

// Layers run bottom to top. Each gap is the clearance below that layer at the default setting.
export function explodeGroupOffsets(layers, anchor, explode) {
  const offsets = layers.map(() => 0);
  if (!explode) return offsets;
  for (let i = anchor + 1; i < layers.length; i++) {
    offsets[i] = Math.max(0, layers[i - 1].maxZ + offsets[i - 1] + layers[i].gap - layers[i].minZ);
  }
  for (let i = anchor - 1; i >= 0; i--) {
    offsets[i] = Math.min(0, layers[i + 1].minZ + offsets[i + 1] - layers[i + 1].gap - layers[i].maxZ);
  }
  const scale = explode / DEFAULT_EXPLODE;
  return offsets.map((offset) => offset * scale);
}

export function toggleFielddeckSheet(current, sheet) {
  return current === sheet ? null : sheet;
}

const clampTo = (value, min, max) => Math.max(min, Math.min(max, value));
const containsPoint = (rect, { x, y }) =>
  x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
const overlaps = (a, b) =>
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
const padRect = (rect, gap) => ({
  left: rect.left - gap, right: rect.right + gap, top: rect.top - gap, bottom: rect.bottom + gap,
});

// A segment can run along the outside edge of a padded obstacle.
function crossesRect(from, to, rect) {
  let enter = 0;
  let exit = 1;
  for (const [start, end, min, max] of [
    [from.x, to.x, rect.left, rect.right], [from.y, to.y, rect.top, rect.bottom],
  ]) {
    if (start === end) {
      if (start <= min || start >= max) return false;
    } else {
      const first = (min - start) / (end - start);
      const last = (max - start) / (end - start);
      enter = Math.max(enter, Math.min(first, last));
      exit = Math.min(exit, Math.max(first, last));
    }
  }
  return enter < exit;
}

function leaderPath(anchor, card, viewport, panels) {
  const edge = {
    x: clampTo(anchor.x, card.left, card.right),
    y: clampTo(anchor.y, card.top, card.bottom),
  };
  const clear = (from, to) => !panels.some((panel) => crossesRect(from, to, panel));
  if (clear(edge, anchor)) return [edge, anchor];

  // Route around blocked straight lines using the visible corners of the panels.
  const corners = panels.flatMap(({ left, right, top, bottom }) => [
    { x: left, y: top }, { x: right, y: top }, { x: left, y: bottom }, { x: right, y: bottom },
  ]).filter((point) => containsPoint(viewport, point));
  const points = [edge, anchor, ...corners];
  const distances = points.map(() => Infinity);
  const previous = [];
  const remaining = new Set(points.keys());
  distances[0] = 0;
  while (remaining.size) {
    const next = [...remaining].reduce((a, b) => distances[a] <= distances[b] ? a : b);
    if (!Number.isFinite(distances[next])) break;
    if (next === 1) {
      const path = [];
      for (let i = 1; i !== undefined; i = previous[i]) path.unshift(points[i]);
      return path;
    }
    remaining.delete(next);
    for (const i of remaining) {
      const distance = distances[next] + Math.hypot(points[next].x - points[i].x, points[next].y - points[i].y);
      if (distance >= distances[i] || !clear(points[next], points[i]) || crossesRect(points[next], points[i], card)) continue;
      distances[i] = distance;
      previous[i] = next;
    }
  }
  return null;
}

// Rectangles and anchors use stage coordinates. A null result folds that card into Details.
export function placeCallouts(viewport, panelRects, callouts) {
  const occupied = [...panelRects];
  const leaderObstacles = panelRects.map((rect) => padRect(rect, 4));
  const center = (viewport.left + viewport.right) / 2;
  return callouts.map(({ width, height, anchor, leftAnchor = anchor, rightAnchor = anchor, outline }) => {
    if (!anchor) return null;
    const maxX = viewport.right - width;
    const maxY = viewport.bottom - height;
    if (maxX < viewport.left || maxY < viewport.top) return null;

    if (outline) {
      const { left, right, top, bottom } = outline;
      const x = (left + right) / 2;
      const y = (top + bottom) / 2;
      const obstacles = occupied.map((rect) => padRect(rect, 4));
      for (const gap of [12, 28, 44]) {
        for (const [rectLeft, rectTop, point] of [
          [right + gap, clampTo(y - height / 2, viewport.top, maxY), { x: right, y }],
          [left - width - gap, clampTo(y - height / 2, viewport.top, maxY), { x: left, y }],
          [clampTo(x - width / 2, viewport.left, maxX), top - height - gap, { x, y: top }],
          [clampTo(x - width / 2, viewport.left, maxX), bottom + gap, { x, y: bottom }],
        ]) {
          const rect = { left: rectLeft, top: rectTop, right: rectLeft + width, bottom: rectTop + height };
          if (!containsPoint(viewport, point) || obstacles.some((obstacle) => containsPoint(obstacle, point))) continue;
          if (rectLeft < viewport.left || rectLeft > maxX || rectTop < viewport.top || rectTop > maxY
            || obstacles.some((obstacle) => overlaps(rect, obstacle))) continue;
          const leader = leaderPath(point, rect, viewport, obstacles);
          if (leader?.length !== 2) continue;
          occupied.push(rect);
          return { rect, leader };
        }
      }
      return null;
    }

    const preferredX = anchor.x < center ? viewport.left + 18 : maxX - 18;
    const preferredY = anchor.y - height / 2;
    for (const gap of [8, 0]) {
      const obstacles = occupied.map((rect) => padRect(rect, gap));
      const panels = gap ? leaderObstacles : panelRects;
      const visible = (point) => containsPoint(viewport, point) && !panels.some((panel) => containsPoint(panel, point));
      const centerPoint = visible(anchor) ? anchor : null;
      const leftPoint = visible(leftAnchor) ? leftAnchor : centerPoint;
      const rightPoint = visible(rightAnchor) ? rightAnchor : centerPoint;
      if (!leftPoint && !rightPoint) continue;
      const anchorGap = Math.max(gap, 1);
      const xs = new Set([preferredX, viewport.left, maxX,
        (leftPoint ?? anchor).x - width - anchorGap, (rightPoint ?? anchor).x + anchorGap,
        ...obstacles.flatMap(({ left, right }) => [left - width, right]),
      ].map((x) => clampTo(x, viewport.left, maxX)));
      const ys = new Set([preferredY, viewport.top, maxY, anchor.y - height - anchorGap, anchor.y + anchorGap,
        ...obstacles.flatMap(({ top, bottom }) => [top - height, bottom]),
      ].map((y) => clampTo(y, viewport.top, maxY)));
      const candidates = [];
      for (const left of xs) {
        for (const top of ys) {
          const rect = { left, top, right: left + width, bottom: top + height };
          const point = left + width / 2 < anchor.x ? leftPoint : rightPoint;
          if (!point || containsPoint(rect, point) || obstacles.some((obstacle) => overlaps(rect, obstacle))) continue;
          const score = Math.abs(top - preferredY) + 0.65 * Math.abs(left - preferredX)
            + (left <= point.x && point.x <= rect.right ? 80 : 0);
          candidates.push({ rect, point, score });
        }
      }
      candidates.sort((a, b) => a.score - b.score);
      for (const { rect, point } of candidates) {
        const leader = leaderPath(point, rect, viewport, panels);
        if (!leader) continue;
        occupied.push(rect);
        return { rect, leader };
      }
    }
    return null;
  });
}

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
