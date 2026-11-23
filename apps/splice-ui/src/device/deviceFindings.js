// What the project's records say about the device as a whole: the part choice, how it fits, how it
// connects. Every finding is built from the scene sidecars (parts, interfaces, blockers,
// alternates, revision diff) and the stage's CAD face measurement; nothing is inferred. Each one
// carries the view that answers it, so choosing a finding composes the model around the question.
import { coverHeadline, coverDetail } from "../components/fielddeckLogic.js";

export const STATES = {
  clash: "collides in CAD",
  failing: "fails KiCad checks",
  checked: "checked by KiCad",
  simulated: "simulated",
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
      answer: sides ? `CAD estimate: ${coverHeadline(sides).replace(/ · computed$/, "")}. Physical fit not tested.` : "Measuring the opening from the CAD model…",
      detail: sides ? ["Stack-up, lug alignment and active-area exposure are not checked by this projection.",
        coverDetail(sides), faceFit.aperture, faceFit.seam].filter(Boolean) : [],
      next: "Print the faceplate and check the display's stack-up and lug alignment against these CAD numbers.",
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
      next: "Attach manufacturer CAD (STEP) or measured dimensions for these parts, then re-measure the fit.",
      view: { mode: target, selected: key(rough[0].part_id), explode: 0.6, also: rough.slice(1, 40).map((part) => key(part.part_id)) },
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
      next: `Resolve before relying on the fit: ${blocker.reason}.`,
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
      next: routing ? "Model the cable paths (or measure them on the printed case) and re-check for interference."
        : "Needs a physical or datasheet answer; record it against this connection.",
      view: link ? { mode: target, selected: linkKey(link.interface_id), explode: 0.45 } : { mode: target, selected: null, explode: 0.6 },
    });
  }

  // Open questions recorded only on the earlier revision: listed too, so every numbered pin has a row.
  if (base && sidecars[base]) {
    const current = new Set(scene.blockers.map((row) => row.reason).concat(scene.interfaces.flatMap((row) => row.open_checks)));
    for (const blocker of sidecars[base].blockers) {
      if (current.has(blocker.reason)) continue;
      fits.push({
        id: `blocker:${base}:${blocker.part_id ?? "device"}:${blocker.reason}`,
        question: `${blocker.part_id ? partLabel(sidecars[base], blocker.part_id) : "Assembly"} (${labelOf(base)} revision)`,
        answer: `${blocker.reason.charAt(0).toUpperCase()}${blocker.reason.slice(1)}.`,
        state: "open",
        basis: blocker.source ?? null,
        reasons: [blocker.reason],
        view: { mode: "compare", selected: blocker.part_id ? `${base}:part:${blocker.part_id}` : null, explode: 0.6 },
      });
    }
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
    next: link.open_checks.length ? `First open check: ${words(link.open_checks[0])}.` : null,
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
  // Every part in a group of pairs, so the whole set shows on the model (capped for legibility).
  const groupView = (rows) => {
    const ids = [...new Set(rows.flatMap((row) => [row.a, row.b]))].slice(0, 40);
    return { mode: revision, selected: key(ids[0]), also: ids.slice(1).map(key), explode: 0 };
  };
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
        next: "Move or resize one of the two parts in CAD and re-measure.",
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
      next: "Replace the stand-in shapes with real part CAD, then re-measure.",
      view: groupView(standIn),
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
      next: "Attach real component heights or 3D models, then re-measure these pairs.",
      view: groupView(tightStandIn),
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
        : `${plural(rows.length, "pair")} at most ${value} mm apart${rows.length > 2 ? ", a repeated gap: possibly a designed seam (intent not recorded)" : ""}${standInOnly ? "; all involve stand-in shapes" : ""}.`,
      detail: rows.slice(0, 6).map((row) => `${name(row.a)} ↔ ${name(row.b)}`).concat(rows.length > 6 ? [`and ${rows.length - 6} more`] : []),
      state: standInOnly ? "unknown" : "computed",
      basis: `minimum gap between surface samples (true gap between ${mm(Math.max(0, first.gap_mm - first.precision_mm))} and ${mm(first.gap_mm)})`,
      next: rows.length > 2 ? "Record whether this gap is intended (a seam) or should be closed." : "Check this clearance against print tolerance and assembly order.",
      view: rows.length > 1 ? groupView(rows) : pairView(first),
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
      view: groupView(touching),
    });
  }
  return [{ id: "measured", title: "Measured from the CAD model", items }];
}

const money = (value) => `$${Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const KICAD_TYPES = {
  shorting_items: "Shorts between nets", unconnected_items: "Unconnected items", clearance: "Clearance violations",
  tracks_crossing: "Crossing tracks", solder_mask_bridge: "Solder-mask bridges", hole_clearance: "Hole clearance",
  schematic_parity: "Board and schematic disagree",
};
const kicadType = (type) => KICAD_TYPES[type] ?? `${words(type).charAt(0).toUpperCase()}${words(type).slice(1)}`;

// KiCad's own DRC/ERC on the board, each violation traced to the parts it touches.
const KICAD_NEXT = {
  shorting_items: "Fix the routing so the two nets no longer share copper, then re-run DRC.",
  unconnected_items: "Route the missing connections (or confirm they are intentionally open), then re-run DRC.",
  clearance: "Move or narrow the copper to meet the board's clearance rule, then re-run DRC.",
  tracks_crossing: "Re-route the crossing tracks on separate layers or around each other.",
  hole_clearance: "Move copper or the hole to meet the hole clearance rule.",
  solder_mask_bridge: "Check pad spacing and solder mask expansion; bridges usually follow from the shorts.",
};

export function kicadFindings(report, { revision } = {}) {
  if (!report) return [];
  const key = (partId) => `${revision}:part:${partId}`;
  const items = [];
  for (const [name, title] of [["drc", "DRC"], ["erc", "ERC"]]) {
    const result = report[name];
    if (!result) continue;
    const errors = result.counts.error ?? 0;
    const warnings = result.counts.warning ?? 0;
    const version = result.kicad_version ? `KiCad ${result.kicad_version}` : "KiCad";
    items.push({
      id: `kicad:${name}`,
      question: `Does the ${name === "drc" ? "board" : "schematic"} pass KiCad's ${title}?`,
      answer: result.total === 0
        ? `${version} reports no ${title} violations. A CAD check, not physical proof.`
        : `No: ${plural(errors, "error")} and ${plural(warnings, "warning")} from ${version}.`,
      state: result.total === 0 ? "checked" : errors ? "failing" : "open",
      basis: `kicad-cli ${name === "drc" ? "pcb drc" : "sch erc"} on ${name === "drc" ? report.board : report.schematic}`,
      view: { mode: revision, selected: null, explode: 0 },
    });
    const byType = new Map();
    for (const row of result.violations) {
      const type = row.group === "unconnected_items" ? "unconnected_items" : row.type;
      if (!byType.has(type)) byType.set(type, []);
      byType.get(type).push(row);
    }
    const order = ["shorting_items", "unconnected_items", "clearance", "tracks_crossing", "hole_clearance", "solder_mask_bridge"];
    const types = [...byType.keys()].sort((a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99));
    for (const type of types) {
      const rows = byType.get(type);
      const errorsHere = rows.filter((row) => row.severity === "error").length;
      const parts = [...new Set(rows.flatMap((row) => row.part_ids ?? []))];
      const first = rows.find((row) => row.part_ids?.length) ?? rows[0];
      // Parts and the copper of the nets involved, so a short shows both nets on the board.
      const highlight = [...new Set([...(first?.part_ids ?? []), ...(first?.net_ids ?? [])])];
      items.push({
        id: `kicad:${name}:${type}`,
        question: `${kicadType(type)} (${title})`,
        answer: `${plural(rows.length, "violation")}${errorsHere ? `, ${errorsHere} of them errors` : ", warnings"}${parts.length ? `, at ${parts.slice(0, 8).map((id) => id.toUpperCase()).join(", ")}${parts.length > 8 ? "…" : ""}` : ""}.`,
        detail: rows.slice(0, 6).map((row) => `${row.description}${row.part_ids?.length ? ` · ${row.part_ids.map((id) => id.toUpperCase()).join(", ")}` : ""}`)
          .concat(rows.length > 6 ? [`and ${rows.length - 6} more`] : []),
        state: errorsHere ? "failing" : "open",
        basis: `${version} ${title}; parts traced from the violation's items and positions`,
        next: KICAD_NEXT[type] ?? null,
        view: highlight.length
          ? { mode: revision, selected: key(highlight[0]), also: highlight.slice(1).map(key), explode: 0 }
          : { mode: revision, selected: null, explode: 0 },
      });
    }
  }
  return items.length ? [{ id: "kicad", title: "Electrical checks (KiCad)", items }] : [];
}

// Strategy, simulation, receipts, external tool runs and cost, from the scene's evidence records.
export function evidenceFindings(records, { revision, partIds = new Set() } = {}) {
  const groups = new Map();
  const add = (group, title, item) => {
    if (!groups.has(group)) groups.set(group, { id: group, title, items: [] });
    groups.get(group).items.push(item);
  };
  const overview = { mode: revision, selected: null, explode: 0.6 };
  for (const record of records ?? []) {
    const source = record.source;
    if (record.error) {
      add("records", "Records", { id: `record:${source}`, question: record.label, answer: `Not readable: ${record.error}.`, state: "unknown", basis: source, view: overview });
      continue;
    }
    if (record.kind === "strategy") {
      for (const option of record.options) {
        const chosen = Object.entries(record.decision).filter(([, value]) => value === option.id).map(([role]) => words(role).replace(/^selected for /, ""));
        add("chosen", "What was chosen", {
          id: `strategy:${option.id}`,
          question: `Option: ${option.label}`,
          answer: `${option.known_usd == null ? "No verified cost" : `${money(option.known_usd)} known`}${option.cost_complete ? "" : `, incomplete: ${option.missing.length} item${option.missing.length === 1 ? "" : "s"} not costed`}.${chosen.length ? ` Chosen as the ${chosen.join(" and ")}.` : ""}`,
          detail: [option.risk && `Risk: ${option.risk}`, option.engineering_status && `Engineering: ${words(option.engineering_status)}`,
            option.procurement_status && `Procurement: ${words(option.procurement_status)}`,
            option.missing.length && `Missing: ${option.missing.join(", ")}`].filter(Boolean),
          state: "recorded",
          basis: option.cost_basis ?? source,
          view: overview,
          canvas: { kind: "strategy", record, focus: option.id },
        });
      }
      if (record.decision.rationale) {
        add("chosen", "What was chosen", {
          id: "strategy:decision",
          question: "Why that strategy?",
          answer: record.decision.rationale,
          detail: [`Procurement approved: ${record.decision.procurement_approved ? "yes" : "no"}`,
            record.constraints?.physical_build_authorized === false ? "Physical build: not authorized" : null].filter(Boolean),
          state: "recorded", basis: source, view: overview,
          canvas: { kind: "strategy", record, focus: null },
        });
      }
    }
    if (record.kind === "simulation") {
      const accepted = record.scenarios.filter((row) => row.accepted).length;
      const describe = (row) => {
        const m = row.metrics;
        const bits = [];
        if (m.seconds != null) bits.push(`${m.seconds} s`);
        if (m.hover_error_m != null) bits.push(`hover error ${(m.hover_error_m * 100).toFixed(1)} cm`);
        if (m.gust_recovery_error_m != null) bits.push(`gust recovery ${(m.gust_recovery_error_m * 100).toFixed(1)} cm`);
        if (m.landing_speed_m_s != null) bits.push(`landing ${m.landing_speed_m_s.toFixed(2)} m/s`);
        if (m.peak_current_a_est != null) bits.push(`peak current ${m.peak_current_a_est.toFixed(1)} A (estimated)`);
        if (m.fault_detected) bits.push("fault detected");
        return `${words(row.id)}: expected ${words(row.expected)}; ${row.accepted ? "behaved as expected" : "did not"} · ${bits.join(", ")}`;
      };
      add("simulated", "Simulated", {
        id: "simulation:missions",
        question: "Does it fly its missions in simulation?",
        answer: `${accepted} of ${record.scenarios.length} scenarios behaved as expected in the simulation${record.scenarios.some((row) => row.motor_failure && row.metrics.fault_detected) ? ", including a motor failure that was detected" : ""}. Not a physical flight${record.authorization?.flight_authorized === false ? "; flight is not authorized" : ""}.`,
        detail: record.scenarios.map(describe),
        state: "simulated",
        basis: source,
        view: { mode: revision, selected: null, explode: 0 },
        canvas: { kind: "simulation", record },
      });
      if (record.scope_limits.length) {
        add("simulated", "Simulated", {
          id: "simulation:limits",
          question: "What does the simulation leave out?",
          answer: record.scope_limits[0],
          detail: record.scope_limits.slice(1),
          state: "recorded", basis: source, view: overview,
        });
      }
    }
    if (record.kind === "design_receipt") {
      const checks = Object.entries(record.checks);
      const nonzero = checks.filter(([, value]) => value);
      add("receipt", "Verification receipt", {
        id: "receipt:checks",
        question: "What did the design verification check?",
        answer: `${checks.length} checks recorded (${nonzero.length ? `${nonzero.length} with issues` : "none with issues"}) by KiCad ${record.toolchain?.kicad_cli ?? ""}. Physical correctness: ${words(record.authority.physical_correctness ?? "unproven").toLowerCase()}; fabrication and power-on not authorized.`,
        detail: [...checks.map(([name, value]) => `${words(name)}: ${value}`), ...record.nonclaims],
        state: nonzero.length ? "open" : "checked",
        basis: source, view: overview,
      });
    }
    if (record.kind === "tool_run") {
      const tool = record.tools[0];
      // Most severe first; info rows go last so real warnings are read before inventory notes.
      const rank = { error: 0, warning: 1, warn: 1, note: 2, info: 3 };
      const ordered = [...record.findings].sort((a, b) => (rank[a.severity] ?? 1.5) - (rank[b.severity] ?? 1.5));
      const warnings = record.findings.filter((row) => row.severity && row.severity !== "info").length;
      const firstWithParts = ordered.find((row) => row.parts.some((ref) => partIds.has(ref.toLowerCase())));
      const keys = firstWithParts ? firstWithParts.parts.map((ref) => ref.toLowerCase()).filter((id) => partIds.has(id)) : [];
      if (tool) {
        add("tools", "External tools", {
          id: `tool:${tool.repository}`,
          question: `What did ${tool.repository.split("/").pop()} find?`,
          answer: `${tool.repository} at ${String(tool.commit_sha).slice(0, 7)} (${tool.license}) ran on this design: ${plural(record.findings.length, "finding")}, ${warnings} above info.`,
          detail: ordered.slice(0, 8).map((row) => `${row.severity}: ${row.message}`)
            .concat(ordered.length > 8 ? [`and ${ordered.length - 8} more`] : []),
          state: "recorded",
          basis: `${source}; commit-pinned, licence-checked run`,
          view: keys.length ? { mode: revision, selected: `${revision}:part:${keys[0]}`, also: keys.slice(1).map((id) => `${revision}:part:${id}`), explode: 0 } : overview,
        });
      }
      for (const row of record.not_run) {
        add("tools", "External tools", {
          id: `tool:not-run:${row.repository}`,
          question: `Why was ${row.repository.split("/").pop()} not run?`,
          answer: `${row.repository} was discovered but not executed: ${row.reason?.toLowerCase() ?? "no reviewed adapter"}.`,
          state: "recorded", basis: source, view: overview,
        });
      }
    }
    if (record.kind === "bom_csv") {
      const priced = record.lines.filter((row) => row.line_usd != null).sort((a, b) => b.line_usd - a.line_usd);
      add("cost", "Cost", {
        id: `bom:${source}`,
        question: `What does it cost? (${record.label})`,
        answer: `${money(record.known_total_usd)} known across ${plural(priced.length, "priced line")}${record.unpriced.length ? `; ${plural(record.unpriced.length, "line")} unpriced, so the true total is higher` : ""}.`,
        detail: [...Object.entries(record.by_basis).map(([basis, value]) => `${basis}: ${money(value)}`),
          ...priced.slice(0, 5).map((row) => `${row.name} · ${money(row.line_usd)}`)],
        state: "recorded",
        basis: source, view: overview,
      });
    }
  }
  return [...groups.values()];
}
