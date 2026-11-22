// What the project's records say about the device as a whole: the part choice, how it fits, how it
// connects. Every finding is built from the scene sidecars (parts, interfaces, blockers,
// alternates, revision diff) and the stage's CAD face measurement; nothing is inferred. Each one
// carries the view that answers it, so choosing a finding composes the model around the question.
import { coverHeadline, coverDetail } from "../components/fielddeckLogic.js";

export const STATES = {
  clash: "collides in CAD",
  computed: "computed from CAD",
  recorded: "recorded",
  open: "open",
  unknown: "unknown",
};

const words = (id) => String(id ?? "").replace(/[_-]+/g, " ").trim();
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function partLabel(sidecar, partId) {
  const part = sidecar?.parts?.find((row) => row.part_id === partId);
  return part ? shortLabel(part.label) : words(partId);
}

// Sidecar labels carry the full product line ("Nano 10000mAh 30W bank, Black Stone; ..."); the
// finding names the thing, and the full label stays in the part card.
export function shortLabel(label = "") {
  // Generated node names ("REFERENCE_ENVELOPE_central_base") read as words, marked as envelopes.
  const envelope = /^REFERENCE_ENVELOPE_/i.test(label);
  const text = envelope ? `${label.replace(/^REFERENCE_ENVELOPE_/i, "").replace(/_/g, " ")} (reference envelope)` : label;
  const head = envelope ? text : text.split(/[;,(]/)[0].trim();
  return head.length > 48 ? `${head.slice(0, 46).trimEnd()}…` : head;
}

const ROUGH = new Set(["envelope", "unknown"]);

// Words that tie a device-level open question to the connection it is about.
const LINK_WORDS = /\b(gpio|usb|dsi|ffc|ribbon|power|cable|fan|keyboard)\b/gi;

function relatedLink(scene, reason) {
  const words = new Set((reason.match(LINK_WORDS) ?? []).map((word) => word.toLowerCase()));
  let best = null;
  let bestScore = 0;
  for (const link of scene.interfaces) {
    const hay = `${link.interface_id} ${link.label}`.toLowerCase();
    const score = [...words].filter((word) => hay.includes(word)).length;
    if (score > bestScore) { best = link; bestScore = score; }
  }
  return best;
}

export function deviceFindings({ sidecars, compare, focusPart, faceFit, labelOf = (rev) => rev }) {
  const target = compare?.target ?? Object.keys(sidecars).at(-1);
  const base = compare?.base ?? null;
  const scene = sidecars[target];
  if (!scene) return [];
  const key = (partId) => `${target}:part:${partId}`;
  const linkKey = (id) => `${target}:link:${id}`;
  const interfaceChecks = new Set(scene.interfaces.flatMap(({ open_checks }) => open_checks));

  // --- What was chosen -----------------------------------------------------------------------
  const chosen = [];
  for (const alternate of scene.alternates ?? []) {
    const current = partLabel(scene, alternate.part_id);
    chosen.push({
      id: `alternate:${alternate.part_id}:${alternate.part}`,
      question: `Why the ${current}?`,
      answer: `${alternate.part} was ${words(alternate.status)}: ${alternate.failed_checks.map(words).join(", ")}.`,
      state: "recorded",
      basis: alternate.source ?? null,
      view: { mode: target, selected: key(alternate.part_id), explode: 0.6 },
    });
  }
  const counts = scene.revision_diff?.counts;
  if (base && counts) {
    const changed = scene.revision_diff.nodes?.find((row) => row.status === "changed");
    const changedPart = changed && scene.parts.find((part) => part.node_name === changed.node_name);
    chosen.push({
      id: "revision-diff",
      question: `What changed from the ${labelOf(base)} revision?`,
      answer: `${plural(counts.changed ?? 0, "part")} changed, ${counts.added ?? 0} added, ${counts.removed ?? 0} removed; ${counts.unchanged ?? 0} unchanged.`,
      state: "computed",
      basis: "revision diff of the two CAD models",
      view: { mode: "compare", selected: changedPart ? key(changedPart.part_id) : null, explode: 1 },
    });
  }

  // --- How it fits ---------------------------------------------------------------------------
  const fits = [];
  if (focusPart) {
    const sides = faceFit?.sides;
    fits.push({
      id: "face-fit",
      question: `Does the ${partLabel(scene, focusPart)} sit in the faceplate opening?`,
      answer: sides ? coverHeadline(sides).replace(/ · computed$/, "") : "Measuring the opening from the CAD model…",
      detail: sides ? [coverDetail(sides), faceFit.aperture, faceFit.seam].filter(Boolean) : [],
      state: sides ? "computed" : "unknown",
      basis: "projected CAD section; physical fit not tested",
      view: { mode: target, selected: key(focusPart), faceView: true, explode: 0 },
    });
  }
  const rough = scene.parts.filter((part) => part.part_id !== "world" && ROUGH.has(part.geometry_basis));
  const roughGroups = new Map();
  for (const part of rough) {
    const group = part.bom_line ?? part.group ?? part.part_id;
    if (!roughGroups.has(group)) roughGroups.set(group, []);
    roughGroups.get(group).push(part);
  }
  if (rough.length) {
    const names = [...roughGroups.values()].map((parts) => shortLabel(parts[0].label));
    fits.push({
      id: "rough-shapes",
      question: "Which parts are only rough shapes?",
      answer: `${names.join(", ")}: modelled as outer envelopes or unknown shapes, so clearances around them are not a real fit.`,
      state: "unknown",
      basis: "geometry basis recorded per part",
      view: { mode: target, selected: key(rough[0].part_id), explode: 0.6 },
    });
  }
  for (const blocker of scene.blockers) {
    if (!blocker.part_id || interfaceChecks.has(blocker.reason)) continue;
    fits.push({
      id: `blocker:${blocker.part_id}:${blocker.reason}`,
      question: `${partLabel(scene, blocker.part_id)}: is it fully specified?`,
      answer: `No. ${blocker.reason.charAt(0).toUpperCase()}${blocker.reason.slice(1)}.`,
      state: "open",
      basis: blocker.source ?? null,
      reasons: [blocker.reason],
      view: { mode: target, selected: key(blocker.part_id), explode: 0.45 },
    });
  }
  for (const blocker of scene.blockers) {
    if (blocker.part_id || interfaceChecks.has(blocker.reason)) continue;
    const routing = /routing|bend/i.test(blocker.reason);
    const link = routing ? scene.interfaces.find((row) => /ribbon|ffc|dsi/i.test(`${row.interface_id} ${row.label}`))
      : relatedLink(scene, blocker.reason);
    fits.push({
      id: `blocker:device:${blocker.reason}`,
      question: routing ? "Do the cables route without interference?"
        : link ? `${link.label}: is it rated for the job?` : "Open question on the assembly",
      answer: `${blocker.reason.charAt(0).toUpperCase()}${blocker.reason.slice(1)}.`,
      state: "open",
      basis: blocker.source ?? null,
      reasons: [blocker.reason],
      view: link ? { mode: target, selected: linkKey(link.interface_id), explode: 0.45 } : { mode: target, selected: null, explode: 0.6 },
    });
  }

  // --- How it connects -----------------------------------------------------------------------
  const connects = scene.interfaces.map((link) => ({
    id: `link:${link.interface_id}`,
    question: `${link.label}: ${partLabel(scene, link.from_part_id)} → ${partLabel(scene, link.to_part_id)}`,
    answer: link.open_checks.length
      ? `${plural(link.open_checks.length, "open check")}; ${link.endpoints_present ? "both ends are in the model" : "an end is missing from the model"}.`
      : `No open checks recorded; ${link.endpoints_present ? "both ends are in the model" : "an end is missing from the model"}. Not tested on hardware.`,
    detail: link.open_checks.map((check) => `${words(check).charAt(0).toUpperCase()}${words(check).slice(1)}`),
    state: link.open_checks.length ? "open" : "recorded",
    basis: link.source ?? null,
    reasons: link.open_checks,
    view: { mode: target, selected: linkKey(link.interface_id), explode: 0.45 },
  }));

  return [
    { id: "chosen", title: "What was chosen", items: chosen },
    { id: "fits", title: "How it fits", items: fits },
    { id: "connects", title: "How it connects", items: connects },
  ].filter((group) => group.items.length);
}

// Search across parts and connections: a designator, a label or a word of either.
export function findTargets(index, revision, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [];
  return [...index.byKey.values()]
    .filter((row) => row.revision === revision && (row.part ? row.part.part_id !== "world" : true))
    .map((row) => {
      const label = row.part ? row.part.label : row.link.label;
      const id = row.part ? row.part.part_id : row.link.interface_id;
      const hay = `${id} ${label}`.toLowerCase();
      const rank = id.toLowerCase() === needle ? 0 : id.toLowerCase().startsWith(needle) ? 1 : hay.includes(needle) ? 2 : -1;
      return { key: row.key, label: shortLabel(label), kind: row.part ? "part" : "connection", rank };
    })
    .filter(({ rank }) => rank >= 0)
    .sort((a, b) => a.rank - b.rank || a.label.localeCompare(b.label))
    .slice(0, 8);
}

const mm = (value) => `${Number(value).toFixed(value < 10 ? 2 : 1)} mm`;

// The measured fit (GET /fit) as questions. Gaps are upper bounds from surface sampling, so a gap
// reads "at most"; a pair involving an envelope or unknown shape is a stand-in result.
export function fitFindings(fit, { sidecar, revision, labelOf = (rev) => rev } = {}) {
  if (!fit) return [];
  const name = (partId) => partLabel(sidecar, partId);
  const key = (partId) => `${revision}:part:${partId}`;
  const pairView = (row) => ({ mode: revision, selected: key(row.a), also: [key(row.b)], explode: 0 });
  const items = [];
  if (fit.size_mm) {
    items.push({
      id: "fit:size",
      question: "How big is the assembled device?",
      answer: `${fit.size_mm.map((value) => Number(value).toFixed(1)).join(" × ")} mm overall, as modelled in the ${labelOf(revision)} revision.`,
      state: "computed",
      basis: `bounding size of ${fit.parts_measured} measured parts`,
      view: { mode: revision, selected: null, explode: 0 },
    });
  }
  const overlaps = fit.pairs.filter((row) => row.kind === "overlap");
  const real = overlaps.filter((row) => !row.stand_in);
  const standIn = overlaps.filter((row) => row.stand_in);
  const open = fit.not_computed.flatMap((row) => row.what === "overlap volume" ? row.parts : []);
  if (real.length) {
    for (const row of real) {
      items.push({
        id: `fit:clash:${row.a}:${row.b}`,
        question: `Do ${name(row.a)} and ${name(row.b)} collide?`,
        answer: `Yes in the CAD model: they overlap by ${Number(row.overlap_mm3).toFixed(1)} mm³.`,
        state: "clash",
        basis: "exact intersection volume of the two solids",
        view: pairView(row),
      });
    }
  } else {
    items.push({
      id: "fit:no-clash",
      question: "Do any real parts collide?",
      answer: `No overlap between solid parts with real geometry in the CAD model${open.length ? `; ${open.map(name).join(", ")} ${open.length === 1 ? "is an open mesh" : "are open meshes"}, so ${open.length === 1 ? "its" : "their"} overlap was not computed` : ""}.`,
      state: open.length ? "unknown" : "computed",
      basis: "exact intersection volume of every nearby pair of solids",
      view: { mode: revision, selected: null, explode: 0 },
    });
  }
  if (standIn.length) {
    items.push({
      id: "fit:stand-in-overlaps",
      question: "Do the rough stand-in shapes overlap?",
      answer: `${plural(standIn.length, "pair")} of envelope or unknown shapes overlap (largest ${Number(Math.max(...standIn.map((row) => row.overlap_mm3))).toFixed(0)} mm³). That says the shapes are not known well enough, not that real parts collide.`,
      detail: standIn.slice(0, 6).map((row) => `${name(row.a)} ↔ ${name(row.b)} · ${Number(row.overlap_mm3).toFixed(0)} mm³`),
      state: "unknown",
      basis: "intersection volume of stand-in shapes",
      view: pairView(standIn[0]),
    });
  }
  // Tight gaps between real shapes, grouped by measured value: a run of identical gaps is usually
  // one designed seam. Tight pairs that involve a stand-in shape go into one item of their own.
  const tightAll = fit.pairs.filter((row) => row.kind === "tight");
  const tightStandIn = tightAll.filter((row) => row.stand_in);
  const tight = tightStandIn.length > 3 ? tightAll.filter((row) => !row.stand_in) : tightAll;
  if (tightStandIn.length > 3) {
    const closest = tightStandIn[0];
    items.push({
      id: "fit:tight-stand-in",
      question: "Which close pairs involve rough stand-in shapes?",
      answer: `${plural(tightStandIn.length, "pair")} under 1 mm apart where at least one part is an envelope or unknown shape (closest at most ${closest.gap_mm.toFixed(2)} mm). Real part shapes are needed before these are fit results.`,
      detail: tightStandIn.slice(0, 6).map((row) => `${name(row.a)} ↔ ${name(row.b)} · ${row.gap_mm.toFixed(2)} mm`).concat(tightStandIn.length > 6 ? [`and ${tightStandIn.length - 6} more`] : []),
      state: "unknown",
      basis: "minimum gap between a part's surface samples and the other part's triangles",
      view: pairView(closest),
    });
  }
  const groups = new Map();
  for (const row of tight) {
    const value = row.gap_mm.toFixed(2);
    if (!groups.has(value)) groups.set(value, []);
    groups.get(value).push(row);
  }
  for (const [value, rows] of [...groups.entries()].sort((a, b) => Number(a[0]) - Number(b[0]))) {
    const standInOnly = rows.every((row) => row.stand_in);
    const first = rows[0];
    items.push({
      id: `fit:tight:${value}`,
      question: rows.length === 1 ? `How close are ${name(first.a)} and ${name(first.b)}?`
        : `Which parts sit ${value} mm apart?`,
      answer: rows.length === 1
        ? `At most ${value} mm apart in the CAD model${first.stand_in ? ", measured on a stand-in shape" : ""}.`
        : `${plural(rows.length, "pair")} at most ${value} mm apart${rows.length > 2 ? ", a repeated gap that is usually a designed seam" : ""}${standInOnly ? "; all involve stand-in shapes" : ""}.`,
      detail: rows.slice(0, 6).map((row) => `${name(row.a)} ↔ ${name(row.b)}`).concat(rows.length > 6 ? [`and ${rows.length - 6} more`] : []),
      state: standInOnly ? "unknown" : "computed",
      basis: `minimum gap between surface samples (true gap between ${mm(Math.max(0, first.gap_mm - first.precision_mm))} and ${mm(first.gap_mm)})`,
      view: pairView(first),
    });
  }
  const touching = fit.pairs.filter((row) => row.kind === "touching");
  if (touching.length) {
    items.push({
      id: "fit:touching",
      question: "Which parts touch?",
      answer: `${plural(touching.length, "pair")} of surfaces meet without measurable overlap: stacked, seated or fastened parts.`,
      detail: touching.slice(0, 6).map((row) => `${name(row.a)} ↔ ${name(row.b)}`).concat(touching.length > 6 ? [`and ${touching.length - 6} more`] : []),
      state: "computed",
      basis: "surface samples closer than 0.05 mm with no overlap volume",
      view: pairView(touching[0]),
    });
  }
  return [{ id: "measured", title: "Measured from the CAD model", items }];
}
