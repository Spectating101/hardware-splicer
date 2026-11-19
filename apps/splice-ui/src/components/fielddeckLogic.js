export const BASIS_LABELS = {
  custom: "Custom CAD",
  vendor_step: "Vendor model",
  donor_cad: "Donor CAD (unverified)",
  measured: "Measured",
  envelope: "Envelope",
  proxy: "Proxy",
  unknown: "Unknown",
};

export const DIFF_LABELS = {
  added: "Added",
  changed: "Changed",
  removed: "Removed",
  unchanged: "Unchanged",
};

export const FIELDDECK_COMPARE = { base: "7", target: "5" };
export const DEFAULT_EXPLODE = 0.6;
export const FIELDDECK_NARROW = "(width < 640px)";
export const QUALITY_SAMPLE_COUNT = 60;

export const DIFF_COLORS = { changed: 0xa78bfa, added: 0x2dd4bf, removed: 0xf17e70 };
export const CREASE_INK = 0x1a1d22;

// Dimmed (unchanged in Compare) values are neutral greys at about 0.72 of the lit value, so the
// largest masses in the frame have cool, readable shadow sides instead of warm taupe.
export const DIMMED_VENDOR = 0x8a8d90;
const VENDOR = { color: 0x9c9ea0, dimmed: DIMMED_VENDOR, roughness: 0.86, threshold: 42 };
const MATERIALS = {
  custom: { color: 0xcec3b0, dimmed: 0x9a9894, roughness: 0.80, threshold: 32 },
  vendor_step: VENDOR,
  donor_cad: VENDOR,
  measured: { color: 0xe4e2dc, roughness: 0.74, threshold: 32, creaseOpacity: 1 },
  envelope: { color: 0xa5aeb5, fillOpacity: 0.06, pattern: [6, 4] },
  proxy: { color: 0xa6a098, roughness: 0.88, threshold: 32, hatch: { angle: 45, spacing: 8, contrast: 0.1 } },
  unknown: { color: null, edgeColor: 0x9097a0, pattern: [3, 2] },
};

// Bases without a listed dimmed value: their luminance grey, fully neutral, at value × 0.72.
export function dimmedColor(hex) {
  const channels = [16, 8, 0].map((shift) => (hex >> shift) & 255);
  const grey = Math.round((0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]) * 0.72);
  return grey * 0x10101;
}

export function materialSpec(basis, delta, dimmed = false) {
  const { color, dimmed: dimmedValue, threshold = 32, creaseOpacity = 0.35, edgeColor = color,
    fillOpacity = 0, pattern = null, roughness, hatch = null } = MATERIALS[basis] ?? MATERIALS.unknown;
  return {
    color: dimmed && color != null ? dimmedValue ?? dimmedColor(color) : color, roughness, metalness: 0, hatch, fillOpacity, pattern,
    threshold, creaseColor: CREASE_INK, creaseOpacity: dimmed ? 0.25 : creaseOpacity,
    edgeColor: pattern ? edgeColor : DIFF_COLORS[delta] ?? CREASE_INK,
  };
}

export function chooseTier(samples, tier = "standard") {
  if (samples.length < QUALITY_SAMPLE_COUNT) return tier;
  const ordered = samples.slice(0, QUALITY_SAMPLE_COUNT).sort((a, b) => a - b);
  const p90 = ordered[Math.ceil(0.9 * QUALITY_SAMPLE_COUNT) - 1];
  if (p90 <= 14) return tier;
  return tier === "high" ? "standard" : "reduced";
}

const difference = (a, b) => a.map((value, axis) => value - b[axis]);
const dot = (a, b) => a.reduce((sum, value, axis) => sum + value * b[axis], 0);
const length = (v) => Math.hypot(...v);

export function weldEdgeChains(positions, tolerance = 0.01) {
  const cells = new Map();
  const vertices = [];
  function vertexFor(point) {
    const [x, y, z] = point.map((value) => Math.floor(value / tolerance));
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (let dz = -1; dz <= 1; dz++) {
          for (const vertex of cells.get(`${x + dx},${y + dy},${z + dz}`) ?? []) {
            if (length(difference(vertex.point, point)) <= tolerance) return vertex;
          }
        }
      }
    }
    const key = `${x},${y},${z}`;
    const vertex = { point, neighbors: new Map() };
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key).push(vertex);
    vertices.push(vertex);
    return vertex;
  }
  for (let i = 0; i < positions.length; i += 6) {
    const a = vertexFor(Array.from(positions.slice(i, i + 3)));
    const b = vertexFor(Array.from(positions.slice(i + 3, i + 6)));
    if (a === b || a.neighbors.has(b)) continue;
    const edge = { used: false };
    a.neighbors.set(b, edge);
    b.neighbors.set(a, edge);
  }
  const chains = [];
  function trace(start, next, edge) {
    const points = [start.point];
    while (edge && !edge.used) {
      edge.used = true;
      points.push(next.point);
      if (next.neighbors.size !== 2) break;
      const onward = [...next.neighbors].find(([, candidate]) => !candidate.used);
      if (!onward) break;
      [next, edge] = onward;
    }
    chains.push(points);
  }
  for (const start of [...vertices.filter(({ neighbors }) => neighbors.size !== 2), ...vertices]) {
    for (const [next, edge] of start.neighbors) {
      if (!edge.used) trace(start, next, edge);
    }
  }
  return chains;
}

export function simplifyEdgeChain(points, tolerance = 0.2) {
  if (points.length < 3) return points.slice();
  const last = points.length - 1;
  const keep = new Set([0, last]);
  const spans = [[0, last]];
  while (spans.length) {
    const [from, to] = spans.pop();
    const axis = difference(points[to], points[from]);
    const squared = dot(axis, axis);
    let farthest = tolerance;
    let split = from;
    for (let i = from + 1; i < to; i++) {
      const offset = difference(points[i], points[from]);
      const t = squared ? Math.min(1, Math.max(0, dot(offset, axis) / squared)) : 0;
      const distance = length(offset.map((value, j) => value - t * axis[j]));
      if (distance <= farthest) continue;
      farthest = distance;
      split = i;
    }
    if (split === from) continue;
    keep.add(split);
    spans.push([from, split], [split, to]);
  }
  const closed = points[0].every((value, i) => value === points[last][i]);
  return closed && keep.size < 4 ? points.slice() : points.filter((_, i) => keep.has(i));
}

export function cullCoincidentChains(chains, positions, { tolerance = 0.15, simplify = false } = {}) {
  // Use the tolerance to find candidates. A nearby, parallel CAD change can still be real.
  const epsilon = Math.min(tolerance, 0.0001);
  const bins = new Map();
  const bin = (x) => Math.floor(x / 5);
  for (let i = 0; i < positions.length; i += 6) {
    const a = Array.from(positions.slice(i, i + 3));
    const b = Array.from(positions.slice(i + 3, i + 6));
    const edge = [a, b];
    for (let j = bin(Math.min(a[0], b[0]) - tolerance); j <= bin(Math.max(a[0], b[0]) + tolerance); j++) {
      if (!bins.has(j)) bins.set(j, []);
      bins.get(j).push(edge);
    }
  }
  function coincides(a, b) {
    const axis = difference(b, a);
    const size = length(axis);
    if (!size) return true;
    const direction = axis.map((value) => value / size);
    const candidates = new Set();
    for (let i = bin(Math.min(a[0], b[0])); i <= bin(Math.max(a[0], b[0])); i++) {
      for (const edge of bins.get(i) ?? []) candidates.add(edge);
    }
    const spans = [];
    for (const edge of candidates) {
      const offsets = edge.map((point) => difference(point, a));
      const [start, end] = offsets.map((v) => dot(v, direction));
      if (Math.max(start, end) < 0 || Math.min(start, end) > size) continue;
      if (offsets.some((v, i) => length(v.map((value, j) => value - (i ? end : start) * direction[j])) > epsilon)) continue;
      spans.push([Math.min(start, end), Math.max(start, end)]);
    }
    let covered = 0;
    spans.sort(([a], [b]) => a - b);
    for (const [start, end] of spans) {
      if (start > covered + epsilon) break;
      covered = Math.max(covered, end);
      if (covered >= size - epsilon) return true;
    }
    return false;
  }
  const remaining = [];
  function append(run) {
    if (run.length < 2) return;
    const shorter = simplify ? simplifyEdgeChain(run) : run;
    // A simplified chord can land on the current edge and hide a small CAD change.
    const hidesChange = shorter.length < run.length
      && shorter.some((end, i) => i > 0 && coincides(shorter[i - 1], end));
    remaining.push(hidesChange ? run : shorter);
  }
  for (const points of chains) {
    let run = [points[0]];
    for (let i = 1; i < points.length; i++) {
      if (coincides(points[i - 1], points[i])) {
        append(run);
        run = [points[i]];
      } else {
        run.push(points[i]);
      }
    }
    append(run);
  }
  return remaining;
}

const chainLength = (points) => points.slice(1).reduce((sum, point, i) => sum + length(difference(point, points[i])), 0);

// Group edge segments into connected components and return the ones that close into a simple loop.
export function closedEdgeLoops(positions, weld = 0.001) {
  const vertices = new Map();
  const vertexFor = (i) => {
    const key = [0, 1, 2].map((axis) => Math.round(positions[i + axis] / weld)).join(",");
    if (!vertices.has(key)) {
      vertices.set(key, { point: [positions[i], positions[i + 1], positions[i + 2]], neighbors: new Set() });
    }
    return vertices.get(key);
  };
  for (let i = 0; i < positions.length; i += 6) {
    const a = vertexFor(i);
    const b = vertexFor(i + 3);
    if (a === b) continue;
    a.neighbors.add(b);
    b.neighbors.add(a);
  }
  const loops = [];
  const seen = new Set();
  for (const start of vertices.values()) {
    if (seen.has(start)) continue;
    const component = [start];
    seen.add(start);
    for (let i = 0; i < component.length; i++) {
      for (const neighbor of component[i].neighbors) {
        if (!seen.has(neighbor)) {
          seen.add(neighbor);
          component.push(neighbor);
        }
      }
    }
    if (component.length < 3 || component.some(({ neighbors }) => neighbors.size !== 2)) continue;
    const points = [start.point];
    let previous = start;
    let current = [...start.neighbors][0];
    while (current !== start) {
      points.push(current.point);
      const next = [...current.neighbors].find((neighbor) => neighbor !== previous);
      previous = current;
      current = next;
    }
    points.push(start.point);
    const min = [0, 1, 2].map((axis) => Math.min(...points.map((point) => point[axis])));
    const max = [0, 1, 2].map((axis) => Math.max(...points.map((point) => point[axis])));
    loops.push({ points, perimeter: chainLength(points), min, max });
  }
  return loops;
}

// A removed or unknown part reads from its outer loop and at most one inner loop (bezel or
// mounting ear). Islands shorter than minPerimeter and a stacked copy of the outer loop are culled.
export function ghostOutlineLoops(positions, { minPerimeter = 15, maxChains = 2, stacked = false } = {}) {
  const area = ({ min, max }) => (max[0] - min[0]) * (max[1] - min[1]);
  const loops = closedEdgeLoops(positions).filter(({ perimeter }) => perimeter >= minPerimeter)
    .sort((a, b) => area(b) - area(a) || b.max[2] - a.max[2]);
  const [outer] = loops;
  if (!outer) return [];
  const within = (loop) => [0, 1].every((axis) =>
    loop.min[axis] >= outer.min[axis] - 0.5 && loop.max[axis] <= outer.max[axis] + 0.5);
  const copy = (loop) => [0, 1].every((axis) =>
    Math.abs(loop.min[axis] - outer.min[axis]) < 1 && Math.abs(loop.max[axis] - outer.max[axis]) < 1);
  const inner = loops.slice(1).filter((loop) => within(loop) && copy(loop) === stacked);
  return [outer, ...inner].slice(0, maxChains).map(({ points }) => points);
}

const isSmallCircle = (points, maxRadius) => {
  if (points.length < 7 || length(difference(points[0], points.at(-1))) > 1e-6) return false;
  const center = [0, 1, 2].map((axis) => points.slice(1).reduce((sum, point) => sum + point[axis], 0) / (points.length - 1));
  const radii = points.map((point) => length(difference(point, center)));
  const radius = radii.reduce((sum, value) => sum + value, 0) / radii.length;
  return radius < maxRadius && radii.every((value) => Math.abs(value - radius) <= radius * 0.15);
};

// Change colour belongs on the outer silhouette and on boundary loops that enclose more than 15%
// of the part's bounds, after a 1e-4 mm weld. Vent slots, small cutouts and hole rims stay in ink,
// and chains under 8 mm are dropped. `extents` is the part's bounding-box size [x, y, z].
export function diffAccentChains(positions, extents, { minLength = 8, minShare = 0.15, rimRadius = 6 } = {}) {
  const [major, minor] = extents.slice().sort((a, b) => b - a);
  return weldEdgeChains(positions, 0.0001).filter((points) => {
    const length = chainLength(points);
    if (length < minLength || isSmallCircle(points, rimRadius)) return false;
    const size = [0, 1, 2].map((axis) => Math.max(...points.map((point) => point[axis]))
      - Math.min(...points.map((point) => point[axis]))).sort((a, b) => b - a);
    // A loop counts by the area it encloses; an open run counts when it is long against the part.
    const closed = length > 0 && points.length > 3 && chainLength([points[0], points.at(-1)]) < 1e-6;
    return size[0] * size[1] >= minShare * major * minor || !closed && length >= 0.3 * major;
  });
}

// Isolated old-revision chains under minLength with no welded neighbour read as specks.
export function cullIsolatedChains(chains, { minLength = 2, weld = 0.01 } = {}) {
  const ends = chains.map((points) => [points[0], points.at(-1)]);
  const touches = (i) => chains.some((_, j) => j !== i && ends[i].some((a) => ends[j].some((b) =>
    length(difference(a, b)) <= weld)));
  return chains.filter((points, i) => chainLength(points) >= minLength || touches(i));
}

export function totalChainLength(chains) {
  return chains.reduce((sum, points) => sum + chainLength(points), 0);
}

// The scene sub-line for a changed part's old revision says what is actually drawn.
export function oldRevisionCaption(visibleLength, before, after) {
  const valid = (stats) => stats && Number.isFinite(stats.volume);
  const volume = valid(before) && valid(after)
    ? ` · ΔV ${signedAmount((after.volume - before.volume) / 1000, 2)} cm³ · computed` : "";
  return `old revision ${visibleLength > 20 ? "dashed" : "coincident"}${volume}`;
}

// Signed tetrahedron sum (mm³) and triangle area (mm²) of an indexed or flat triangle list.
export function meshMeasures(positions, index = null) {
  let volume = 0;
  let area = 0;
  const count = index ? index.length : positions.length / 3;
  const at = (i, axis) => positions[(index ? index[i] : i) * 3 + axis];
  for (let i = 0; i + 2 < count; i += 3) {
    const [ax, ay, az] = [0, 1, 2].map((axis) => at(i, axis));
    const [bx, by, bz] = [0, 1, 2].map((axis) => at(i + 1, axis));
    const [cx, cy, cz] = [0, 1, 2].map((axis) => at(i + 2, axis));
    volume += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6;
    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    area += Math.hypot(uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx) / 2;
  }
  return { volume, area };
}

function signedAmount(delta, digits) {
  const amount = Math.abs(delta).toFixed(digits);
  return `${Number(amount) === 0 ? "" : delta < 0 ? "−" : "+"}${amount}`;
}

export function meshDeltaLabel(before, after) {
  const valid = (stats) => stats && Number.isFinite(stats.volume) && Number.isFinite(stats.area);
  if (!valid(before) || !valid(after)) return null;
  return `ΔV ${signedAmount((after.volume - before.volume) / 1000, 2)} cm³ · ΔA ${signedAmount((after.area - before.area) / 100, 2)} cm²`;
}

// Screen-space helpers for annotations. Points are { x, y } in stage pixels.
export function convexHull(points) {
  const sorted = points.slice().sort((a, b) => a.x - b.x || a.y - b.y);
  if (sorted.length < 3) return sorted;
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower = [];
  for (const point of sorted) {
    while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), point) <= 0) lower.pop();
    lower.push(point);
  }
  const upper = [];
  for (const point of sorted.reverse()) {
    while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), point) <= 0) upper.pop();
    upper.push(point);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

export function nearestPoint(points, target) {
  let best = null;
  let distance = Infinity;
  for (const point of points) {
    const next = Math.hypot(point.x - target.x, point.y - target.y);
    if (next < distance) {
      distance = next;
      best = point;
    }
  }
  return best;
}

// Corner brackets around a tight screen box: arms of `arm` px, pushed `offset` px outward.
export function bracketPath(points, { arm = 10, offset = 8 } = {}) {
  if (!points.length) return "";
  const left = Math.min(...points.map(({ x }) => x)) - offset;
  const right = Math.max(...points.map(({ x }) => x)) + offset;
  const top = Math.min(...points.map(({ y }) => y)) - offset;
  const bottom = Math.max(...points.map(({ y }) => y)) + offset;
  return [[left, top, 1, 1], [right, top, -1, 1], [right, bottom, -1, -1], [left, bottom, 1, -1]]
    .map(([x, y, dx, dy]) => `M${x + arm * dx},${y}H${x}v${arm * dy}`).join(" ");
}

// The Routing unknown pill sits beside endpoint B with no connecting line.
export function placeBesideEndpoint(viewport, obstacles, point, width, height, gap = 16) {
  const candidates = [
    [point.x + gap, point.y - height / 2], [point.x - gap - width, point.y - height / 2],
    [point.x - width / 2, point.y - gap - height], [point.x - width / 2, point.y + gap],
  ];
  for (const radius of [0, 24, 48]) {
    for (const [left, top] of candidates) {
      const dx = Math.sign(left + width / 2 - point.x) * radius;
      const dy = Math.sign(top + height / 2 - point.y) * radius;
      const rect = { left: left + dx, top: top + dy, right: left + dx + width, bottom: top + dy + height };
      if (rect.left < viewport.left || rect.right > viewport.right || rect.top < viewport.top
        || rect.bottom > viewport.bottom || obstacles.some((obstacle) => overlaps(rect, obstacle))) continue;
      return { x: rect.left + width / 2, y: rect.top + height / 2 };
    }
  }
  return null;
}

// Screen-space repulsion for pins: centres at least minDistance apart and each pin (radius px)
// at least `clearance` px outside every obstacle rectangle. Fixed points push but never move.
export function repelPins(points, { minDistance = 24, obstacles = [], clearance = 12, radius = 12, iterations = 60 } = {}) {
  const out = points.map((point) => ({ ...point }));
  for (let step = 0; step < iterations; step++) {
    let moved = false;
    for (let i = 0; i < out.length; i++) {
      for (let j = i + 1; j < out.length; j++) {
        const a = out[i];
        const b = out[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance >= minDistance - 1e-6 || a.fixed && b.fixed) continue;
        if (!distance) [dx, dy, distance] = [1, 0, 1];
        const push = (minDistance - distance) / (a.fixed || b.fixed ? 1 : 2);
        if (!a.fixed) { a.x -= dx / distance * push; a.y -= dy / distance * push; }
        if (!b.fixed) { b.x += dx / distance * push; b.y += dy / distance * push; }
        moved = true;
      }
    }
    for (const point of out) {
      if (point.fixed) continue;
      for (const rect of obstacles) {
        const pad = clearance + radius;
        const left = rect.left - pad;
        const right = rect.right + pad;
        const top = rect.top - pad;
        const bottom = rect.bottom + pad;
        if (point.x <= left || point.x >= right || point.y <= top || point.y >= bottom) continue;
        const exits = [[point.x - left, left, point.y], [right - point.x, right, point.y],
          [point.y - top, point.x, top], [bottom - point.y, point.x, bottom]].sort((m, n) => m[0] - n[0]);
        [, point.x, point.y] = exits[0];
        moved = true;
      }
    }
    if (!moved) break;
  }
  return out;
}

// Pair each old-revision feature with the nearest new feature of the same size, only when the
// match is unambiguous: nearest within maxDistance and no other candidate within ratio × that.
// Features are { center: [x, y, z], size }.
// The two rims of one hole (same axis, same size) are one feature: keep the upper rim.
export function mergeCoaxialFeatures(features, { axisTolerance = 0.5, sizeTolerance = 0.2 } = {}) {
  const merged = [];
  for (const feature of features.slice().sort((a, b) => b.center[2] - a.center[2])) {
    const coaxial = merged.some(({ center, size }) => Math.abs(size - feature.size) <= sizeTolerance
      && Math.hypot(center[0] - feature.center[0], center[1] - feature.center[1]) <= axisTolerance);
    if (!coaxial) merged.push(feature);
  }
  return merged;
}

export function pairMovedFeatures(olderFeatures, newerFeatures, { maxDistance = 25, ratio = 1.5, sizeTolerance = 0.2 } = {}) {
  const older = mergeCoaxialFeatures(olderFeatures, { sizeTolerance });
  const newer = mergeCoaxialFeatures(newerFeatures, { sizeTolerance });
  const pairs = [];
  for (const feature of older) {
    const candidates = newer.filter(({ size }) => Math.abs(size - feature.size) <= sizeTolerance)
      .map((candidate) => ({ candidate, distance: length(difference(candidate.center, feature.center)) }))
      .sort((a, b) => a.distance - b.distance);
    const [nearest, second] = candidates;
    if (!nearest || nearest.distance > maxDistance) continue;
    if (second && second.distance <= nearest.distance * ratio) continue;
    pairs.push([feature, nearest.candidate]);
  }
  return pairs;
}

export function countClippedItems(items, { top, bottom }) {
  return items.filter((item) => item.top < top || item.bottom > bottom).length;
}

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

// Scale around the unobstructed rectangle's centre. A value below 1 means an edge clips.
export function projectedFitScale(bounds, rect, margin = 0) {
  const { x: marginX, y: marginY } = typeof margin === "number" ? { x: margin, y: margin } : margin;
  const halfWidth = (rect.right - rect.left) / 2;
  const halfHeight = (rect.bottom - rect.top) / 2;
  const x = rect.left + halfWidth;
  const y = rect.top + halfHeight;
  return Math.min(
    Math.max(1, halfWidth - marginX) / Math.max(x - bounds.left, bounds.right - x),
    Math.max(1, halfHeight - marginY) / Math.max(y - bounds.top, bounds.bottom - y),
  );
}

export function footprintDelta(older, newer) {
  const difference = (axis) => {
    const delta = (newer.max[axis] - newer.min[axis]) - (older.max[axis] - older.min[axis]);
    const magnitude = Math.abs(delta).toFixed(2);
    return `${delta < 0 && magnitude !== "0.00" ? "−" : "+"}${magnitude} mm`;
  };
  return `Width ${difference("x")} · Height ${difference("y")}`;
}

export function dimensionLabel(revision, bounds, axis) {
  const value = bounds.max[axis] - bounds.min[axis];
  return `${revision}-inch · ${formatEvidenceValue({ field: "dimension_mm", value })} · computed`;
}

const clampTo = (value, min, max) => Math.max(min, Math.min(max, value));
const containsPoint = (rect, { x, y }) =>
  x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
const overlaps = (a, b) =>
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
const padRect = (rect, gap) => ({
  left: rect.left - gap, right: rect.right + gap, top: rect.top - gap, bottom: rect.bottom + gap,
});

export function placeRoutingLabel(viewport, panels, pins, midpoint, width, height) {
  const pinObstacles = pins.map((rect) => padRect(rect, 12));
  const left = Math.min(...pinObstacles.map((rect) => rect.left));
  const top = Math.min(...pinObstacles.map((rect) => rect.top));
  const bottom = Math.max(...pinObstacles.map((rect) => rect.bottom));
  const maxX = viewport.right - width;
  const maxY = viewport.bottom - height;
  const x = clampTo(midpoint.x - width / 2, viewport.left, maxX);
  const y = clampTo(midpoint.y - height / 2, viewport.top, maxY);
  const obstacles = [...pinObstacles, ...panels];
  const xs = [x, viewport.left, maxX, ...obstacles.flatMap((rect) => [rect.left - width, rect.right])]
    .sort((a, b) => Math.abs(a - x) - Math.abs(b - x));
  const ys = [y, viewport.top, maxY, ...obstacles.flatMap((rect) => [rect.top - height, rect.bottom])]
    .sort((a, b) => Math.abs(a - y) - Math.abs(b - y));
  for (const [col, row] of [
    ...xs.map((candidate) => [candidate, top - height]),
    ...ys.filter((candidate) => candidate + height / 2 >= top + 12 && candidate + height / 2 <= bottom - 12)
      .map((candidate) => [left - width, candidate]),
    ...xs.map((candidate) => [candidate, bottom]),
    // A scattered cluster can leave usable space between the pins.
    ...ys.flatMap((row) => xs.map((col) => [col, row])),
  ]) {
    const rect = { left: col, right: col + width, top: row, bottom: row + height };
    if (col >= viewport.left && col <= maxX && row >= viewport.top && row <= maxY
      && !obstacles.some((obstacle) => overlaps(rect, obstacle))) {
      return { x: col + width / 2, y: row + height / 2 };
    }
  }
  return null;
}

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

function leaderPath(anchor, card, viewport, panels, elbow) {
  const edge = {
    x: clampTo(anchor.x, card.left, card.right),
    y: clampTo(anchor.y, card.top, card.bottom),
  };
  const clear = (from, to) => !panels.some((panel) => crossesRect(from, to, panel));
  if (elbow) {
    const side = anchor.x < (card.left + card.right) / 2 ? card.left : card.right;
    const top = anchor.y < (card.top + card.bottom) / 2 ? card.top : card.bottom;
    const middleX = (card.left + card.right) / 2;
    const middleY = (card.top + card.bottom) / 2;
    for (const [start, bend] of [
      [{ x: side, y: middleY }, { x: anchor.x, y: middleY }],
      [{ x: middleX, y: top }, { x: middleX, y: anchor.y }],
    ]) {
      if (!crossesRect(start, bend, card) && !crossesRect(bend, anchor, card)
        && clear(start, bend) && clear(bend, anchor)) return [start, bend, anchor];
    }
    return null;
  }
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
export function placeCallouts(viewport, panelRects, callouts, clearSpace = []) {
  const occupied = [...panelRects, ...clearSpace];
  const leaderObstacles = panelRects.map((rect) => padRect(rect, 4));
  const center = (viewport.left + viewport.right) / 2;
  return callouts.map(({ width, height, anchor, leftAnchor = anchor, rightAnchor = anchor, outline, elbow, model }) => {
    if (!anchor) return null;
    const maxX = viewport.right - width;
    const maxY = viewport.bottom - height;
    if (maxX < viewport.left || maxY < viewport.top) return null;

    if (model) {
      const leftSide = anchor.x < (model.left + model.right) / 2;
      const obstacles = occupied.map((rect) => padRect(rect, 8));
      const point = leftSide ? leftAnchor : rightAnchor;
      if (!containsPoint(viewport, point)) return null;
      const idealY = anchor.y - height / 2;
      const ys = [clampTo(idealY, viewport.top, maxY),
        ...obstacles.flatMap(({ top, bottom }) => [top - height, bottom]),
      ].sort((a, b) => Math.abs(a - idealY) - Math.abs(b - idealY));
      for (const gap of [40, 64, 88, 112, 140]) {
        const left = leftSide ? model.left - gap - width : model.right + gap;
        if (left < viewport.left || left > maxX) continue;
        for (const top of ys) {
          const rect = { left, top, right: left + width, bottom: top + height };
          if (top < viewport.top || top > maxY || obstacles.some((obstacle) => overlaps(rect, obstacle))) continue;
          const leader = leaderPath(point, rect, viewport, leaderObstacles, true);
          const length = leader?.slice(1).reduce((sum, p, i) =>
            sum + Math.hypot(p.x - leader[i].x, p.y - leader[i].y), 0);
          if (!leader || length > 160) continue;
          occupied.push(rect);
          return { rect, leader };
        }
      }
      return null;
    }

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
    const preferredY = anchor.y - height / 2 - (elbow ? height : 0);
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
        const leader = leaderPath(point, rect, viewport, panels, elbow);
        if (!leader) continue;
        occupied.push(rect);
        return { rect, leader };
      }
    }
    return null;
  });
}

export function classifyPart(part, delta, mode) {
  let basis = Object.hasOwn(BASIS_LABELS, part.geometry_basis) ? part.geometry_basis : "unknown";
  if (basis === "measured" && !(part.feature_id && part.evidence?.some((record) =>
    record.state === "measured" && record.feature_id === part.feature_id && record.instrument && record.date))) {
    basis = "unknown";
  }
  if (basis === "donor_cad" && /^REFERENCE_ENVELOPE/i.test(part.node_name)) basis = "envelope";
  const diff = mode === "compare" ? delta : undefined;
  const outline = diff === "removed" || basis === "envelope" || basis === "unknown";
  return { basis, diff, outline, dimmed: diff === "unchanged" };
}

// Revision-qualified keys distinguish the two displays, which share a part_id.
export function indexFielddeck(scenes, compare = FIELDDECK_COMPARE) {
  const byKey = new Map();
  const byNode = new Map();
  const byPart = new Map();
  const { nodes = [] } = scenes[compare?.target]?.revision_diff ?? scenes[compare?.base]?.revision_diff ?? {};
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

export function rowsForMode(index, mode, compare = FIELDDECK_COMPARE) {
  return [...index.byKey.values()].filter((row) =>
    mode === "compare"
      ? row.revision === compare?.target || row.part && row.delta === "removed"
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

export function openQuestions(scenes, index) {
  const questions = new Map();
  function add(kind, id, key, reason) {
    const identity = JSON.stringify([kind, id, reason]);
    if (!questions.has(identity)) questions.set(identity, { reason, number: questions.size + 1, keys: new Set() });
    questions.get(identity).keys.add(key);
  }
  for (const revision of ["5", "7"]) {
    const scene = scenes[revision];
    if (!scene) continue;
    for (const { part_id, node_name, interface_id, reason } of scene.blockers) {
      if (interface_id) add("link", interface_id, `${revision}:link:${interface_id}`, reason);
      else {
        const part = index.byPart.get(`${revision}:${part_id}`)
          ?? index.byNode.get(revision)?.get(node_name)?.[0];
        const id = part_id ?? part?.part.part_id ?? node_name;
        add("part", id, part?.key ?? `${revision}:part:${id}`, reason);
      }
    }
    for (const { interface_id, open_checks } of scene.interfaces) {
      for (const reason of open_checks) add("link", interface_id, `${revision}:link:${interface_id}`, reason);
    }
  }
  return [...questions.values()];
}

export function ghostDeltaKey(index, mode, row, compare = FIELDDECK_COMPARE) {
  if (!compare || mode !== "compare" || !row?.part || row.delta !== "changed") return null;
  const revision = row.revision === compare.target ? compare.base : compare.target;
  const { part_id, node_name } = row.part;
  const occurrence = index.byNode.get(row.revision)?.get(node_name)?.indexOf(row);
  return (index.byPart.get(`${revision}:${part_id}`)
    ?? index.byNode.get(revision)?.get(node_name)?.[occurrence])?.key ?? null;
}

// Only deterministic deltas: outer bounds from the sidecars and, when the stage has loaded both
// GLB meshes, their volume and surface area. Never a claim that features or holes moved.
export function changeSummary(index, row, compare, meshStats = null) {
  if (!compare || row?.delta !== "changed") return null;
  const counterpart = index.byKey.get(ghostDeltaKey(index, "compare", row, compare));
  const older = row.revision === compare.base ? row : counterpart;
  const newer = row.revision === compare.target ? row : counterpart;
  const title = `Changed from ${compare.base}-inch revision`;
  const mesh = meshDeltaLabel(meshStats?.get(older?.key), meshStats?.get(newer?.key));
  const meshBounds = (entry) => entry?.part.evidence.find(({ field, state }) =>
    field === "mesh_bounds_mm" && state === "computed")?.value;
  const before = meshBounds(older);
  const after = meshBounds(newer);
  const valid = (bounds) => Array.isArray(bounds) && bounds.length === 6 && bounds.every(Number.isFinite);
  if (!valid(before) || !valid(after)) return { title, bounds: null, mesh };
  const deltas = [0, 1, 2].map((i) => (after[i + 3] - after[i]) - (before[i + 3] - before[i]));
  if (deltas.every((delta) => Math.abs(delta) < 0.01)) {
    return { title, bounds: "Outer bounds unchanged · mesh differs", mesh };
  }
  const bounds = ["X", "Y", "Z"].map((axis, i) => `d${axis} ${signedAmount(deltas[i], 2)}`).join(" · ");
  return { title, bounds: `Bounds · ${bounds} mm`, mesh };
}

const SHORT_NAMES = {
  "keyboard-nominal-envelope": "Keyboard envelope",
  "power-bank-nominal-envelope": "Power bank envelope",
  "pi4-board-envelope": "Raspberry Pi 4",
  "fan-envelope": "Fan envelope",
};

export function shortPartName(part, revision) {
  if (part.part_id === "display") return `${revision}-inch display`;
  return SHORT_NAMES[part.part_id] ?? (part.label.length <= 24 && !/nominal only/i.test(part.label)
    ? part.label
    : "Selected part");
}

export function evidenceLabel(field) {
  const words = field.replace(/_(mm3|mm|w)$/, "").replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
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
  if (typeof value === "string" && Object.hasOwn(BASIS_LABELS, value)) return BASIS_LABELS[value];
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
