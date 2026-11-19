import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FieldDeckScene, { EvidenceRows } from "./FieldDeckScene.jsx";
import {
  bracketPath, changeSummary, cullIsolatedChains, dimmedColor, oldRevisionCaption, totalChainLength, chooseTier, classifyPart, closedEdgeLoops, convexHull, countClippedItems,
  cullCoincidentChains, DEFAULT_EXPLODE, diffAccentChains, DIFF_COLORS, dimensionLabel, evidenceCells,
  explodeGroupOffsets, FIELDDECK_NARROW, footprintDelta, formatEvidenceSource, formatEvidenceValue, ghostOutlineLoops,
  indexFielddeck, materialSpec, meshDeltaLabel, meshMeasures, nearestPoint, placeBesideEndpoint, placeCallouts,
  placeRoutingLabel, projectedFitScale, rowForNode, rowsForMode, selectedPartKeys, simplifyEdgeChain,
  toggleFielddeckSheet, weldEdgeChains,
} from "./fielddeckLogic.js";

const stageMock = vi.hoisted(() => ({ load: vi.fn(), create: vi.fn() }));
vi.mock("three", () => ({}));
vi.mock("./fielddeckStage.js", () => ({
  loadFielddeck: stageMock.load,
  createFielddeckStage: stageMock.create,
  disposeFielddeck: vi.fn(),
}));

function part(part_id, node_name, geometry_basis, extra = {}) {
  return {
    part_id, node_name, geometry_basis, label: part_id, bom_line: part_id,
    evidence: [], explode_vector_mm: [0, 0, 10], ...extra,
  };
}
const meshBounds = (value) => ({ field: "mesh_bounds_mm", state: "computed", value });
const sides = {
  "7": {
    parts: [
      part("display", "PANEL_7", "vendor_step", { label: "7-inch panel" }),
      part("tray", "Tray", "custom", {
        label: "Rear tray", explode_derived: true, evidence: [meshBounds([0, 0, 0, 40, 30, 5])],
      }),
    ],
    blockers: [{ part_id: "display", reason: "Check pilot hole engagement" }],
    interfaces: [{
      interface_id: "display-ribbon", label: "DSI FFC", from_part_id: "pi4-dsi", to_part_id: "display",
      open_checks: ["pin_mapping_unknown", "connector_retention_unknown"],
    }],
  },
  "5": {
    parts: [
      part("display", "Panel 5", "vendor_step", {
        label: "Touch Display 2, 5-inch · nominal only",
        evidence: [{ field: "physical_fit", state: "unknown", value: null }],
      }),
      part("pi4-dsi", "pi4_dsi", "envelope", { label: "Pi DSI port" }),
      part("tray", "Tray", "custom", {
        label: "Rear tray", explode_derived: true, evidence: [meshBounds([1, 0, 0, 39, 30, 6])],
      }),
    ],
    blockers: [
      { part_id: "display", reason: "Display lug thread/engagement nominal only" },
      { interface_id: "display-ribbon", reason: "pin_mapping_unknown" },
    ],
    interfaces: [{
      interface_id: "display-ribbon", label: "DSI FFC", from_part_id: "pi4-dsi", to_part_id: "display",
      open_checks: ["pin_mapping_unknown", "signal_voltage_unknown"],
    }],
    revision_diff: {
      status: "available",
      counts: { added: 1, changed: 1, removed: 1, unchanged: 1 },
      nodes: [
        { node_name: "PANEL_7", occurrence: 1, status: "removed" },
        { node_name: "Panel 5", occurrence: 1, status: "added" },
        { node_name: "pi4_dsi", occurrence: 1, status: "unchanged" },
        { node_name: "Tray", occurrence: 1, status: "changed" },
      ],
    },
  },
};

describe("Fielddeck state and mapping", () => {
  const index = indexFielddeck(sides);

  it("uses added teal only on the edges of a matte vendor part", () => {
    expect(materialSpec("vendor_step", "added")).toMatchObject({
      color: 0x93a3ae, roughness: 0.86, metalness: 0, creaseColor: 0x1a1d22, edgeColor: 0x2dd4bf,
    });
    expect(materialSpec("vendor_step", "unchanged", true)).toMatchObject({ color: dimmedColor(0x93a3ae), creaseOpacity: 0.25 });
    expect(materialSpec("custom", "unchanged", true)).toMatchObject({ color: dimmedColor(0xcec3b0) });
    expect(materialSpec("custom", "changed")).toMatchObject({ color: 0xcec3b0, edgeColor: 0xa78bfa });
    expect(materialSpec("donor_cad", "added")).toEqual(materialSpec("vendor_step", "added"));
    expect(materialSpec("measured")).toMatchObject({ color: 0xe4e2dc, creaseOpacity: 1 });
    expect(materialSpec("proxy").hatch).toEqual({ angle: 45, spacing: 8, contrast: 0.1 });
    for (const basis of ["custom", "vendor_step", "envelope", "proxy", "unknown", "measured", "donor_cad"]) {
      for (const delta of Object.keys(DIFF_COLORS)) {
        const { color, creaseColor, edgeColor } = materialSpec(basis, delta);
        expect([color, creaseColor, edgeColor]).not.toContain(0xf59e0b);
        expect([color, creaseColor]).not.toContain(0x2dd4bf);
      }
    }
  });

  it("requires an instrument and date for the exact measured feature", () => {
    const feature = { geometry_basis: "measured", feature_id: "lip" };
    const record = { state: "measured", feature_id: "lip", instrument: "caliper", date: "2026-11-19" };
    expect(classifyPart({ ...feature, evidence: [record] }).basis).toBe("measured");
    expect(classifyPart({ ...feature, evidence: [{ ...record, feature_id: "foot" }] }).basis).toBe("unknown");
    expect(classifyPart({ geometry_basis: "custom", evidence: [record] }).basis).toBe("custom");
    expect(classifyPart({ geometry_basis: "donor_cad", node_name: "REFERENCE_ENVELOPE_DONOR" }).basis).toBe("envelope");
  });

  it("chooses one tier from the first 60 timings and uses a strict p90 threshold", () => {
    const times = Array(60).fill(14);
    times.fill(20, 0, 6);
    expect(chooseTier(times.slice(0, 59))).toBe("standard");
    expect(chooseTier([...times, ...Array(60).fill(99)])).toBe("standard");
    times[6] = 14.01;
    expect(chooseTier(times)).toBe("reduced");
    expect(chooseTier(times, "high")).toBe("standard");
    expect(chooseTier(times, "reduced")).toBe("reduced");
  });

  it("welds reversed and near endpoints into a continuous chain and retains its turn", () => {
    const [chain] = weldEdgeChains([0, 0, 0, 1.009, 0.02, 0, 2, 0, 0, 1.011, 0.02, 0, 2, 0, 0, 2, 2, 0]);
    expect(chain).toEqual([[0, 0, 0], [1.009, 0.02, 0], [2, 0, 0], [2, 2, 0]]);
    expect(simplifyEdgeChain(chain)).toEqual([[0, 0, 0], [2, 0, 0], [2, 2, 0]]);
  });

  it("culls coincident runs across tessellation splits and keeps small real changes", () => {
    const chain = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]];
    const current = [
      0, 0, 0, 1, 0, 0, 2, 0, 0, 1, 0, 0,
      2, 0, 0, 2, 1.95, 0, 2, 2.04, 0, 0, 2.04, 0,
    ];
    expect(cullCoincidentChains([chain], current)).toEqual([chain.slice(1)]);
    expect(cullCoincidentChains([[[0, 0, 0], [2, 0, 0]]], [1, -1, 0, 1, 1, 0]))
      .toEqual([[[0, 0, 0], [2, 0, 0]]]);
    const bump = [[0, 0, 0], [1, 0.1, 0], [2, 0, 0]];
    expect(cullCoincidentChains([bump], current, { simplify: true })).toEqual([bump]);
  });

  it("reports only sidecar mesh evidence in a changed part's summary", () => {
    const compare = { base: "7", target: "5" };
    expect(changeSummary(index, index.byKey.get("5:part:tray"), compare)).toEqual({
      title: "Changed from 7-inch revision", bounds: "Bounds · dX −2.00 · dY 0.00 · dZ +1.00 mm", mesh: null,
    });
    expect(changeSummary(index, index.byKey.get("5:part:display"), compare)).toBeNull();
    expect(changeSummary(indexFielddeck({ "5": sides["5"] }), index.byKey.get("5:part:tray"), compare))
      .toEqual({ title: "Changed from 7-inch revision", bounds: null, mesh: null });
  });

  it("says outer bounds are unchanged and adds computed mesh deltas from both revisions", () => {
    const compare = { base: "7", target: "5" };
    const same = structuredClone(sides);
    same["5"].parts.find(({ part_id }) => part_id === "tray").evidence = [meshBounds([0, 0, 0, 40, 30, 5.004])];
    const sameIndex = indexFielddeck(same);
    const stats = new Map([
      ["7:part:tray", { volume: 12000, area: 3000 }], ["5:part:tray", { volume: 10750, area: 3012.5 }],
    ]);
    expect(changeSummary(sameIndex, sameIndex.byKey.get("5:part:tray"), compare, stats)).toEqual({
      title: "Changed from 7-inch revision", bounds: "Outer bounds unchanged · mesh differs",
      mesh: "ΔV −1.25 cm³ · ΔA +0.13 cm²",
    });
    expect(meshDeltaLabel({ volume: 5, area: 5 }, { volume: 5.001, area: 5 })).toBe("ΔV 0.00 cm³ · ΔA 0.00 cm²");
    expect(meshDeltaLabel(undefined, { volume: 1, area: 1 })).toBeNull();
  });

  it("measures a closed mesh by signed tetrahedra and triangle area", () => {
    // A 10 mm cube, outward-wound, indexed.
    const positions = [0, 0, 0, 10, 0, 0, 10, 10, 0, 0, 10, 0, 0, 0, 10, 10, 0, 10, 10, 10, 10, 0, 10, 10];
    const index = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7];
    const { volume, area } = meshMeasures(positions, index);
    expect(volume).toBeCloseTo(1000);
    expect(area).toBeCloseTo(600);
    const flat = index.flatMap((i) => positions.slice(i * 3, i * 3 + 3));
    expect(meshMeasures(flat).volume).toBeCloseTo(1000);
  });

  it("reduces a removed part's ghost to its outer loop and one inner loop", () => {
    const rect = (x0, y0, x1, y1, z) => [
      x0, y0, z, x1, y0, z, x1, y0, z, x1, y1, z, x1, y1, z, x0, y1, z, x0, y1, z, x0, y0, z,
    ];
    const positions = [
      ...rect(0, 0, 100, 60, 5), ...rect(0, 0, 100, 60, 4), // glass top and its stacked copy
      ...rect(5, 5, 95, 55, 2), // bezel or PCB loop
      ...rect(10, 10, 20, 20, 1), // a smaller inner loop beyond the cap
      ...rect(30, 30, 32, 32, 1), // 8 mm island
      0, 0, 0, 50, 0, 0, // an open tab edge
    ];
    expect(closedEdgeLoops(positions)).toHaveLength(5);
    const loops = ghostOutlineLoops(positions);
    expect(loops).toHaveLength(2);
    expect(loops[0]).toHaveLength(5);
    expect(loops[0].every(([, , z]) => z === 5)).toBe(true);
    expect(loops[1].every(([, , z]) => z === 2)).toBe(true);
    expect(ghostOutlineLoops(positions, { stacked: true }).map((loop) => loop[0][2])).toEqual([5, 4]);
    expect(ghostOutlineLoops(positions, { maxChains: 1 })).toHaveLength(1);
    expect(ghostOutlineLoops([0, 0, 0, 1, 0, 0])).toEqual([]);
  });

  it("keeps change colour on the outline and large loops and leaves slots, rims and short chains in ink", () => {
    const circle = Array.from({ length: 16 }, (_, i) => {
      const a = (i / 16) * Math.PI * 2;
      const b = ((i + 1) / 16) * Math.PI * 2;
      return [2 * Math.cos(a), 2 * Math.sin(a), 0, 2 * Math.cos(b), 2 * Math.sin(b), 0];
    }).flat();
    const rect = (x0, y0, x1, y1) => [x0, y0, 5, x1, y0, 5, x1, y0, 5, x1, y1, 5, x1, y1, 5, x0, y1, 5, x0, y1, 5, x0, y0, 5];
    const positions = [
      ...rect(0, 0, 100, 60), // outer boundary
      ...rect(10, 10, 60, 40), // large opening: 25% of the bounds
      ...rect(70, 10, 74, 30), // vent slot
      90, 80, 0, 90, 80, 6, // a short free-standing edge
      50, 50, 10, 55, 50, 10, // 5 mm chain
      ...circle,
    ];
    const kept = diffAccentChains(positions, [100, 60, 5]);
    expect(kept).toHaveLength(2);
    expect(kept.every((chain) => chain.length === 5)).toBe(true);
    expect(kept.map((chain) => Math.max(...chain.map(([x]) => x)))).toEqual(expect.arrayContaining([100, 60]));
  });

  it("drops isolated old-revision specks and names the old revision by what is drawn", () => {
    const speck = [[0, 0, 0], [1, 0, 0]];
    const joined = [[1, 0, 0], [1, 1, 0]];
    const arc = [[10, 0, 0], [20, 0, 0], [20, 15, 0]];
    expect(cullIsolatedChains([speck, joined, arc])).toEqual([speck, joined, arc]);
    expect(cullIsolatedChains([speck, arc])).toEqual([arc]);
    expect(totalChainLength([arc])).toBe(25);
    const before = { volume: 12000 };
    const after = { volume: 11450 };
    expect(oldRevisionCaption(25, before, after)).toBe("old revision dashed · ΔV −0.55 cm³ · computed");
    expect(oldRevisionCaption(12, before, after)).toBe("old revision coincident · ΔV −0.55 cm³ · computed");
    expect(oldRevisionCaption(0)).toBe("old revision coincident");
  });

  it("dims unchanged parts toward their luminance grey", () => {
    expect(dimmedColor(0xcec3b0)).toBe(0x7b7977);
    expect(dimmedColor(0x93a3ae)).toBe(0x626465);
  });

  it("frames a tight bracket from projected points and anchors leaders on the hull", () => {
    const points = [{ x: 10, y: 20 }, { x: 50, y: 25 }, { x: 30, y: 60 }, { x: 30, y: 30 }];
    expect(bracketPath(points)).toBe("M12,12H2v10 M48,12H58v10 M48,68H58v-10 M12,68H2v-10");
    expect(bracketPath([])).toBe("");
    const hull = convexHull(points);
    expect(hull).toHaveLength(3);
    expect(hull).not.toContainEqual({ x: 30, y: 30 });
    expect(nearestPoint(hull, { x: 0, y: 0 })).toEqual({ x: 10, y: 20 });
  });

  it("puts Routing unknown beside endpoint B without overlapping pins or panels", () => {
    const viewport = { left: 0, right: 400, top: 0, bottom: 300 };
    expect(placeBesideEndpoint(viewport, [], { x: 100, y: 100 }, 80, 20)).toEqual({ x: 156, y: 100 });
    const right = { left: 110, right: 200, top: 80, bottom: 120 };
    expect(placeBesideEndpoint(viewport, [right], { x: 100, y: 100 }, 80, 20)).toEqual({ x: 44, y: 100 });
    expect(placeBesideEndpoint({ left: 0, right: 60, top: 0, bottom: 40 }, [], { x: 30, y: 20 }, 80, 20)).toBeNull();
  });

  it("counts clipped rows, including a row that is only partly visible", () => {
    const blockers = Array.from({ length: 13 }, (_, i) => ({ top: i * 20, bottom: (i + 1) * 20 }));
    expect(countClippedItems(blockers, { top: 0, bottom: 45 })).toBe(11);
    expect(countClippedItems(blockers, { top: 5, bottom: 45 })).toBe(12);
  });

  it("names the Face view revisions in dimensions computed from their bounds", () => {
    expect(dimensionLabel("7", { min: { x: 60.34 }, max: { x: 249.66 } }, "x"))
      .toBe("7-inch · 189.32 mm · computed");
    expect(dimensionLabel("5", { min: { x: 83.3 }, max: { x: 226.7 } }, "x"))
      .toBe("5-inch · 143.4 mm · computed");
  });

  it("places Routing unknown above, left, or below its pins with 12px clearance", () => {
    const viewport = { left: 0, right: 300, top: 0, bottom: 200 };
    const pins = [{ left: 120, right: 144, top: 76, bottom: 100 }, { left: 156, right: 180, top: 100, bottom: 124 }];
    const midpoint = { x: 150, y: 100 };
    const above = { left: 0, right: 300, top: 0, bottom: 76 };
    const left = { left: 0, right: 120, top: 76, bottom: 124 };
    expect(placeRoutingLabel(viewport, [], pins, midpoint, 100, 20)).toEqual({ x: 150, y: 54 });
    expect(placeRoutingLabel(viewport, [above], pins, midpoint, 100, 20)).toEqual({ x: 58, y: 100 });
    expect(placeRoutingLabel(viewport, [above, left], pins, midpoint, 100, 20)).toEqual({ x: 150, y: 146 });
  });

  it("keeps sidecar geometry basis separate from compare state", () => {
    expect(classifyPart(sides["5"].parts[0], "added", "5")).toEqual({
      basis: "vendor_step", diff: undefined, outline: false, dimmed: false,
    });
    expect(classifyPart(sides["5"].parts[1], "unchanged", "compare")).toEqual({
      basis: "envelope", diff: "unchanged", outline: true, dimmed: true,
    });
    expect(classifyPart({ geometry_basis: "unknown" }, "added", "compare")).toMatchObject({
      outline: true, dimmed: false,
    });
    expect(classifyPart(sides["7"].parts[0], "removed", "compare")).toMatchObject({ outline: true });
    expect(classifyPart(sides["5"].parts[2], "changed", "compare")).toMatchObject({ outline: false, diff: "changed" });
  });

  it("maps exact GLB names, differentiates the displays and resolves both interface endpoints", () => {
    expect(rowForNode(index, "5", "Panel_5")).toBeUndefined();
    const display = rowForNode(index, "5", "Panel 5");
    expect(index.byKey.get(display.key)).toBe(display);
    expect(display.delta).toBe("added");
    const removed = rowForNode(index, "7", "PANEL_7");
    expect(removed.key).not.toBe(display.key);
    expect(rowsForMode(index, "compare")).toContain(removed);
    const link = index.byKey.get("5:link:display-ribbon");
    expect(selectedPartKeys(index, link)).toEqual(["5:part:pi4-dsi", display.key]);
  });
});

describe("Fielddeck stage layout", () => {
  const rect = (left, top, right, bottom) => ({ left, top, right, bottom });
  const card = (x, y, width = 228, height = 115) => ({ width, height, anchor: { x, y } });
  const overlaps = (a, b) =>
    a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

  it("fits off-centre projected bounds inside the stage margins", () => {
    const desktop = rect(200, 100, 696, 596);
    expect(projectedFitScale(rect(148, 248, 548, 448), desktop, 48)).toBeCloseTo(2 / 3);
    expect(projectedFitScale(rect(348, 148, 548, 548), desktop, 48)).toBe(1);
    expect(projectedFitScale(rect(348, 248, 548, 448), desktop, 48)).toBe(2);

    const phone = rect(0, 88, 390, 772);
    expect(projectedFitScale(rect(-33, 230, 309, 630), phone, 24)).toBe(0.75);
  });

  const layers = [
    { minZ: -6, maxZ: 0, gap: 0 },
    { minZ: 3, maxZ: 6, gap: 8 },
    { minZ: 0, maxZ: 80, gap: 8 },
    { minZ: 61, maxZ: 66, gap: 44 },
    { minZ: 47, maxZ: 52, gap: 19 },
    { minZ: 46, maxZ: 62, gap: 29 },
  ];

  it("computes signed footprint deltas from the display bounds", () => {
    const older = { min: { x: -4, y: 6 }, max: { x: 185.32, y: 126.24 } };
    const newer = { min: { x: 10, y: -5 }, max: { x: 153.4, y: 86.46 } };
    expect(footprintDelta(older, newer)).toBe("Width −45.92 mm · Height −28.78 mm");
    expect(footprintDelta(newer, older)).toBe("Width +45.92 mm · Height +28.78 mm");
  });

  it("keeps the presentation layers in height order with clear gaps at the default explode", () => {
    const offsets = explodeGroupOffsets(layers, 2, DEFAULT_EXPLODE);
    expect(offsets[2]).toBe(0);
    for (let i = 1; i < layers.length; i++) {
      const bottom = layers[i].minZ + offsets[i];
      const previousTop = layers[i - 1].maxZ + offsets[i - 1];
      expect(bottom - previousTop).toBeGreaterThanOrEqual(layers[i].gap);
    }
    expect(explodeGroupOffsets(layers, 2, 1)).toEqual(offsets.map((offset) => offset * (1 / DEFAULT_EXPLODE)));
  });

  it("returns zero offsets for every group in the assembled view", () => {
    expect(explodeGroupOffsets(layers, 2, 0)).toEqual([0, 0, 0, 0, 0, 0]);
  });

  it("places a drafting label beside the outline and falls back when its short leaders are blocked", () => {
    const viewport = rect(0, 0, 700, 400);
    const outline = rect(320, 150, 380, 250);
    const label = { ...card(350, 200, 100, 30), outline };
    const [placement] = placeCallouts(viewport, [rect(400, 0, 700, 400)], [label]);
    expect(placement).toEqual({
      rect: rect(208, 185, 308, 215),
      leader: [{ x: 308, y: 200 }, { x: 320, y: 200 }],
    });
    expect(placeCallouts(rect(290, 130, 410, 270), [], [label])).toEqual([null]);
  });

  it("keeps model labels on the anchor side with short leaders and vertical clearance", () => {
    const viewport = rect(0, 0, 800, 400);
    const model = rect(300, 80, 480, 330);
    const label = { ...card(440, 180, 100, 24), rightAnchor: { x: 470, y: 180 }, model };
    const panel = rect(650, 0, 800, 400);
    const [first, second] = placeCallouts(viewport, [panel], [label, label]);
    expect(first.rect.left - model.right).toBe(40);
    expect(Math.abs(first.rect.top - second.rect.top)).toBeGreaterThanOrEqual(32);
    for (const { leader } of [first, second]) {
      expect(leader).toHaveLength(3);
      expect(leader.at(-1)).toEqual(label.rightAnchor);
      expect(leader.slice(1).reduce((sum, p, i) =>
        sum + Math.hypot(p.x - leader[i].x, p.y - leader[i].y), 0)).toBeLessThanOrEqual(160);
    }
  });

  it("flips and stacks cards around the inspector, tree, header and controls", () => {
    const viewport = rect(0, 0, 1426, 900);
    const panels = [
      rect(0, 0, 1426, 58), rect(18, 58, 238, 502),
      rect(1146, 58, 1408, 508), rect(0, 818, 1426, 900),
    ];
    const inputs = [card(1060, 140), card(1060, 140), card(240, 485), card(260, 510)];
    const placements = placeCallouts(viewport, panels, inputs);
    expect(placements.every(Boolean)).toBe(true);
    expect(placements[0].rect.right).toBeLessThan(inputs[0].anchor.x);
    expect(placements[1].rect.right).toBeLessThan(inputs[1].anchor.x);
    expect(placements[1].rect.top).not.toBe(placements[0].rect.top);
    placements.forEach(({ rect: placed, leader }, i) => {
      expect(placed.left).toBeGreaterThanOrEqual(viewport.left);
      expect(placed.top).toBeGreaterThanOrEqual(viewport.top);
      expect(placed.right).toBeLessThanOrEqual(viewport.right);
      expect(placed.bottom).toBeLessThanOrEqual(viewport.bottom);
      expect(panels.some((panel) => overlaps(panel, placed))).toBe(false);
      expect(placements.slice(0, i).some((other) => overlaps(other.rect, placed))).toBe(false);
      expect(leader.at(-1)).toEqual(inputs[i].anchor);
    });
  });

  it("routes the leader around a panel between the card and its anchor", () => {
    const panel = rect(430, 75, 500, 300);
    const panels = [rect(0, 0, 195, 400), rect(195, 0, 405, 95), rect(195, 160, 405, 400), panel];
    const input = card(420, 110, 180, 160);
    const [placement] = placeCallouts(rect(0, 0, 700, 400), panels, [input]);
    expect(placement.rect.left).toBeGreaterThan(panel.right);
    expect(placement.leader.at(-1)).toEqual(input.anchor);
    expect(placement.leader.slice(1, -1).every(({ y }) => y < panel.top)).toBe(true);
    expect(placement.leader.length).toBeGreaterThan(2);
  });

  it("uses the visible viewport and folds cards without a free slot or a visible anchor", () => {
    const viewport = rect(50, 75, 350, 275);
    const panels = [rect(50, 75, 210, 275)];
    const inputs = [card(220, 160, 150, 50), card(80, 160, 80, 50), card(230, 60, 80, 50)];
    expect(placeCallouts(viewport, panels, inputs)).toEqual([null, null, null]);
    const [placement] = placeCallouts(viewport, panels, [card(220, 160, 140, 60)]);
    expect(placement.rect.left).toBe(210);
    expect(placement.rect.right).toBe(350);
  });

  it("switches directly between narrow-screen sheets and closes the active sheet", () => {
    const parts = toggleFielddeckSheet(null, "parts");
    const details = toggleFielddeckSheet(parts, "details");
    expect(parts).toBe("parts");
    expect(details).toBe("details");
    expect(toggleFielddeckSheet(details, "parts")).toBe("parts");
    expect(toggleFielddeckSheet(details, "details")).toBeNull();
  });
});

describe("Fielddeck evidence formatting", () => {
  it("rounds measurements without padding decimals and gives dimensions and power their units", () => {
    expect(formatEvidenceValue({ field: "landscape_glass_mm", value: [143.4, 91.46000003] }))
      .toBe("143.4 × 91.46 mm");
    expect(formatEvidenceValue({ field: "documented_power_w", value: 1.40000001 })).toBe("1.4 W");
    expect(formatEvidenceValue({ field: "nominal_volume_mm3", value: 7565.626 })).toBe("7565.63 mm³");
  });

  it("pairs bounds by axis and leaves the source values intact", () => {
    const value = [83.30000305175781, 164.27000427246094, 46.099998474121094, 226.7, 255.73, 62];
    expect(formatEvidenceValue({ field: "mesh_bounds_mm", value, state: "computed" }))
      .toBe("X 83.3→226.7 · Y 164.27→255.73 · Z 46.1→62 mm");
    expect(value[0]).toBe(83.30000305175781);
  });

  it("uses short source labels with complete destinations", () => {
    const url = "https://www.example.com/data/display.pdf?revision=2";
    expect(formatEvidenceSource(url)).toEqual({ label: "example.com", href: url });
    expect(formatEvidenceSource("docs/MODEL3D.md")).toEqual({
      label: "MODEL3D.md", href: "https://github.com/Spectating101/hardware-splicer/blob/main/docs/MODEL3D.md",
    });
    expect(formatEvidenceSource("digital_v1/design.json").href)
      .toMatch(/\/projects\/cyberdeck-real-trial-20261020\/digital_v1\/design\.json$/);
  });

  it("preserves unknown and the evidence state labels", () => {
    expect(evidenceCells({ field: "power_w", value: 4, state: "unknown", source: null }))
      .toEqual(["power_w", "unknown", "unknown", { label: "unknown" }]);
    expect(evidenceCells({ field: "power_w", value: 3, state: "assumed", source: null }))
      .toEqual(["power_w", "3 W", "assumed", { label: "unknown" }]);
  });
});

describe("Fielddeck evidence UI", () => {
  let narrow;
  let callbacks;
  const update = vi.fn();
  beforeEach(() => {
    narrow = false;
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Scene manifest unavailable")));
    vi.stubGlobal("matchMedia", vi.fn((query) => ({
      matches: query === FIELDDECK_NARROW ? narrow : query === "(prefers-reduced-motion: reduce)",
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    })));
    stageMock.load.mockResolvedValue(Object.fromEntries(
      Object.entries(sides).map(([rev, sidecar]) => [rev, { sidecar, gltf: {} }]),
    ));
    stageMock.create.mockImplementation((_host, _assets, index, handlers) => {
      callbacks = handlers;
      handlers.onFrame();
      return {
        linked: new Set([...index.byKey.values()].filter(({ part }) => part).map(({ key }) => key)),
        meshStats: new Map([["7:part:tray", { volume: 12000, area: 3000 }], ["5:part:tray", { volume: 11450, area: 2990 }]]),
        ghostLengths: new Map([["7:part:tray", 42]]),
        update, dispose: vi.fn(),
      };
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("uses the scene manifest for the heading, tour and view availability", async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        schema: "hardware_splicer.scene_manifest.v1",
        title: "Project scene title", subtitle: "Project scene subtitle", compare: null,
        tour: [{ label: "Inspect the tray", select: "tray", revision: "7", explode: 0.25 }],
      }),
    });
    render(<FieldDeckScene />);
    expect(await screen.findByRole("heading", { name: "Project scene title" })).toBeVisible();
    expect(screen.getByText("Project scene subtitle")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Compare" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Face view" })).toBeNull();
    expect(await screen.findByText("Inspect the tray")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start tour" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({
      mode: "7", explode: 0.25, selectedKey: "7:part:tray",
    }));
  });

  it("renders unknown values and preserves known fields and sources", () => {
    render(<EvidenceRows evidence={[
      { field: "pin_mapping", value: false, state: "unknown", source: null },
      { field: "documented_power_w", value: 1.4, state: "datasheet", source: "brief.pdf" },
      { field: "geometry_reference", value: "vendor_step", state: "computed" },
    ]} />);
    const unknown = screen.getByText("Pin mapping").parentElement;
    expect(unknown).toHaveAttribute("title", "pin_mapping");
    expect(within(unknown).getByText("Unknown")).toHaveClass("fd-evidence-state");
    expect(screen.getByText("Vendor model")).toBeVisible();
    const power = screen.getByText("Documented power").parentElement;
    expect([...power.children].map((node) => node.textContent))
      .toEqual(["Documented power", "datasheet", "1.4 W", "brief.pdf"]);
    expect(within(power).getByRole("link", { name: "brief.pdf" })).toBeVisible();
  });

  it("lists donor and measured sources only in views with those linked geometries", async () => {
    const target = {
      ...sides["5"],
      parts: [...sides["5"].parts, part("donor", "Donor", "donor_cad"), part("lip", "Lip", "measured", {
        feature_id: "lip",
        evidence: [{ state: "measured", feature_id: "lip", instrument: "caliper", date: "2026-11-19" }],
      })],
    };
    stageMock.load.mockResolvedValue({ "7": { sidecar: sides["7"], gltf: {} }, "5": { sidecar: target, gltf: {} } });
    render(<FieldDeckScene />);
    const legend = within(screen.getByRole("group", { name: "Shape source" }));
    expect(await legend.findByText("Donor CAD (unverified)")).toBeVisible();
    expect(legend.getByText("Measured")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "7-inch" }));
    expect(legend.queryByText("Donor CAD (unverified)")).toBeNull();
    expect(legend.queryByText("Measured")).toBeNull();
  });

  it("groups revision changes and syncs picks with the tree and inspector", async () => {
    render(<FieldDeckScene />);
    const panel = screen.getByRole("complementary", { name: "Part tree" });
    const tree = within(panel);
    expect(tree.getByRole("button", { name: "Assembly" })).toHaveAttribute("aria-expanded", "true");
    const tray = await tree.findByRole("button", { name: "Rear tray" });
    expect(tree.getAllByRole("region").map((group) => group.getAttribute("aria-label"))).toEqual([
      "Added", "Changed", "Removed", "Unchanged", "Interfaces", "Blockers",
    ]);
    expect(tree.getByRole("heading", { name: "Added 1" })).toBeVisible();
    expect(tree.getByRole("heading", { name: "Removed 1" })).toBeVisible();
    const unchanged = tree.getByRole("button", { name: /Unchanged \(1\)/ });
    expect(unchanged).toHaveAttribute("aria-expanded", "false");
    expect(tree.queryByRole("button", { name: "Pi DSI port" })).toBeNull();
    fireEvent.click(unchanged);
    expect(tree.getByRole("button", { name: "Pi DSI port" })).toBeVisible();

    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    act(() => callbacks.onPick("5:part:tray"));
    expect(tray).toHaveAttribute("aria-pressed", "true");
    expect(inspector.getByText("Custom CAD · changed")).toBeVisible();
    const evidence = inspector.getByLabelText("Evidence");
    expect([...evidence.firstElementChild.children].map((node) => node.textContent)).toEqual([
      "Changed from 7-inch revision", "computed", "Bounds · dX −2.00 · dY 0.00 · dZ +1.00 mm",
    ]);
    const shapeSource = within(screen.getByRole("group", { name: "Shape source" }));
    expect(shapeSource.queryByText("Donor CAD (unverified)")).toBeNull();
    expect(shapeSource.queryByText("Measured")).toBeNull();
    expect(inspector.queryByText(/^Presentation offset$/)).toBeNull();
    expect(inspector.queryByRole("heading", { name: "Open questions" })).toBeNull();
    expect(panel.querySelectorAll("[data-row][aria-pressed=true]")).toHaveLength(1);
    expect(screen.getByRole("slider", { name: "Explode" })).toHaveValue("0.6");
    expect(screen.getByTestId("fielddeck-scene")).not.toHaveTextContent(/\b(?:ready|verified|measured)\b/i);
  });

  it("shows the presentation offset only while exploded and keeps the slider name", async () => {
    render(<FieldDeckScene />);
    const slider = await screen.findByRole("slider", { name: "Explode" });
    expect(screen.getByText("Presentation offset · 60%")).toBeVisible();
    fireEvent.change(slider, { target: { value: "0" } });
    expect(screen.queryByText(/Presentation offset ·/)).toBeNull();
    expect(screen.getByText("0%")).toBeVisible();
    fireEvent.change(slider, { target: { value: "0.27" } });
    expect(screen.getByText("Presentation offset · 27%")).toBeVisible();
    expect(slider).toHaveAccessibleName("Explode");
  });

  it("marks cable endpoints A and B in the tree and connects their callouts to the markers", async () => {
    render(<FieldDeckScene />);
    fireEvent.click(await screen.findByRole("button", { name: "DSI FFC" }));
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    expect(inspector.getByRole("heading", { name: "Endpoint components" })).toBeVisible();
    expect(inspector.getByText("Routing unknown")).toBeVisible();
    expect(inspector.getByText("A").parentElement).toHaveTextContent("Pi DSI port");
    expect(inspector.getByText("B").parentElement).toHaveTextContent("Touch Display 2, 5-inch · nominal only");
    expect(inspector.getByText("Signal voltage unknown")).toBeVisible();
    const annotations = screen.getByLabelText("Scene callouts");
    expect(within(annotations).getByLabelText("Endpoint A").parentElement)
      .toHaveAttribute("data-pin-anchor", "5:part:pi4-dsi");
    expect(within(annotations).getByLabelText("Endpoint B").parentElement)
      .toHaveAttribute("data-pin-anchor", "5:part:display");
    expect(annotations.querySelector('[data-endpoint-label="A"]')).toHaveTextContent("Pi DSI port");
    expect(annotations.querySelector('[data-endpoint-label="B"]')).toHaveTextContent("5-inch display");
    const label = annotations.querySelector("[data-route-label]");
    expect(label).toHaveTextContent("Routing unknown");
    expect(label.querySelector("path")).toBeNull();
    expect(annotations.querySelector("[data-route-leaders]")).toBeNull();
    expect(annotations.querySelector('[data-question-number="1"]').parentElement).toHaveAttribute("data-dimmed", "true");
    expect(annotations.querySelector('[data-question-number="2"]').parentElement).toHaveAttribute("data-dimmed", "false");
    const tree = screen.getByRole("complementary", { name: "Part tree" });
    expect(tree.querySelectorAll("[data-row][aria-pressed=true]")).toHaveLength(1);
    expect(tree.querySelector('[data-row="5:part:pi4-dsi"][data-endpoint-row="A"] .fd-endpoint')).toHaveTextContent(/^A$/);
    expect(tree.querySelector('[data-row="5:part:display"][data-endpoint-row="B"] .fd-endpoint')).toHaveTextContent(/^B$/);
    expect(tree.querySelector('[data-row="5:part:tray"]')).not.toHaveAttribute("data-endpoint-row");
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({
      selectedKeys: ["5:part:pi4-dsi", "5:part:display"],
    }));
  });

  it("numbers each question once across revisions and counts only questions in the visible mode", async () => {
    render(<FieldDeckScene />);
    fireEvent.click(await screen.findByRole("button", { name: "DSI FFC" }));
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    const mapping = () => inspector.getByText("Pin mapping unknown").parentElement;
    expect(mapping()).toHaveTextContent(/^2 · DSI FFC\s*Pin mapping unknown$/);
    expect(inspector.getByText("Connector retention unknown")).toBeVisible();
    expect(screen.getByRole("button", { name: "Physical fit unknown · 5 open questions" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "7-inch" }));
    expect(mapping()).toHaveTextContent(/^2 · DSI FFC\s*Pin mapping unknown$/);
    expect(inspector.queryByText("Signal voltage unknown")).toBeNull();
    expect(inspector.getByText("A").parentElement).toHaveTextContent("pi4-dsi");
    expect(screen.getByRole("button", { name: "Physical fit unknown · 3 open questions" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "5-inch" }));
    expect(mapping()).toHaveTextContent(/^2 · DSI FFC\s*Pin mapping unknown$/);
    expect(inspector.queryByText("Connector retention unknown")).toBeNull();
    expect(screen.getByRole("button", { name: "Physical fit unknown · 3 open questions" })).toBeVisible();
  });

  it("toggles Face view and requests ghost geometry only for changed parts in Compare", async () => {
    render(<FieldDeckScene />);
    fireEvent.click(await screen.findByRole("button", { name: "Face view" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ faceView: true, ghostDeltaKey: null }));
    expect(screen.getByText("5-inch minus 7-inch · CAD footprint, computed")).toBeInTheDocument();
    const scene = screen.getByTestId("fielddeck-scene");
    expect(scene.querySelector('[data-question-number="1"]').parentElement).toHaveAttribute("data-pin-anchor", "5:part:display");
    expect(scene.querySelector('[title="Check pilot hole engagement"]').parentElement).toHaveAttribute("data-pin-anchor", "7:part:display");
    fireEvent.click(screen.getByRole("button", { name: "Back to 3D" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ faceView: false }));
    fireEvent.click(screen.getByRole("button", { name: "Rear tray" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ ghostDeltaKey: "7:part:tray" }));
    expect(screen.getByText("old revision dashed · ΔV −0.55 cm³ · computed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "5-inch" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ ghostDeltaKey: null }));
    fireEvent.click(screen.getByRole("button", { name: "Compare" }));
    fireEvent.click(screen.getByRole("button", { name: /Unchanged \(1\)/ }));
    fireEvent.click(screen.getByRole("button", { name: "Pi DSI port" }));
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({ ghostDeltaKey: null }));
  });

  it("uses the same blocker number on the pin, tree and inspector and keeps the qualifier intact", async () => {
    render(<FieldDeckScene />);
    const filter = await screen.findByRole("button", { name: "Physical fit unknown · 5 open questions" });
    const scene = screen.getByTestId("fielddeck-scene");
    const pin = scene.querySelector('[data-question-number="1"]');
    expect(pin).toHaveTextContent(/^1$/);
    expect(pin.closest("[data-pin-anchor]")).toHaveAttribute("data-pin-anchor", "5:part:display");
    expect([...scene.querySelectorAll("[data-anchor]")].map((label) => label.textContent)).toEqual(["5-inch display"]);
    fireEvent.click(await screen.findByRole("button", { name: "Rear tray" }));
    expect([...scene.querySelectorAll("[data-anchor]")].map((label) => label.textContent)).toEqual([
      "Rear trayold revision dashed · ΔV −0.55 cm³ · computed",
    ]);
    expect(scene.querySelector("[data-anchor] .fd-label-detail")).toHaveTextContent(/^old revision dashed · ΔV/);
    expect(scene.querySelectorAll("[data-leader]")).toHaveLength(1);
    fireEvent.click(pin);
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    expect(inspector.getByRole("heading", { name: "Touch Display 2, 5-inch · nominal only" })).toBeVisible();
    const name = inspector.getByRole("heading", { name: "Touch Display 2, 5-inch · nominal only" });
    const fit = inspector.getByText("Physical fit · Unknown");
    const metadata = inspector.getByText("Vendor model · added");
    expect(name.nextElementSibling).toBe(fit);
    expect(fit.nextElementSibling).toBe(metadata);
    expect(metadata.nextElementSibling).toHaveTextContent("Open questions");
    expect(inspector.getByText("Check pilot hole engagement").closest("li")).toHaveTextContent("7-inch revision");
    expect(inspector.getByRole("heading", { name: "Evidence" }).previousElementSibling).toBe(inspector.getByText("Check pilot hole engagement").closest("ul"));
    expect(inspector.queryByText(/^Physical fit$/)).toBeNull();
    expect(inspector.getByText("Display lug thread/engagement nominal only").previousElementSibling)
      .toHaveTextContent(/^1 · 5-inch display$/);
    fireEvent.click(filter);
    const tree = within(screen.getByRole("complementary", { name: "Part tree" }));
    expect(filter).toHaveAttribute("aria-pressed", "true");
    expect(tree.queryByRole("region", { name: "Added" })).toBeNull();
    expect(tree.getByRole("button", { name: "1 Display lug thread/engagement nominal only" }))
      .toHaveAttribute("data-linked", "true");
    fireEvent.click(screen.getByRole("button", { name: "7-inch" }));
    expect(scene.querySelector('[title="Check pilot hole engagement"]')).toBeInTheDocument();
  });

  it("switches between narrow sheets and keeps the current selection in the peek", async () => {
    narrow = true;
    render(<FieldDeckScene />);
    const more = await screen.findByRole("button", { name: "More" });
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("slider", { name: "Explode" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Fielddeck display swap" })).toBeVisible();
    expect(screen.queryByText("7-inch → 5-inch")).toBeNull();
    expect(screen.getByRole("button", { name: "Face view" })).toHaveClass("fd-face-pill");
    expect(screen.getByText("Presentation offset · 60%", { selector: ".fd-offset-caption" })).toBeVisible();
    fireEvent.click(more);
    expect(screen.getByRole("slider", { name: "Explode" })).toBeVisible();
    expect(within(document.getElementById("fd-options")).getByRole("button", { name: "Face view" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Start tour" })).toBeVisible();
    const key = screen.getByRole("button", { name: "Key" });
    expect(key).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(key);
    expect(screen.getByRole("group", { name: "Shape source" })).toBeVisible();
    fireEvent.click(key);
    fireEvent.click(screen.getByRole("button", { name: "Next stop" }));
    expect(more).toHaveAttribute("aria-expanded", "false");
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({
      selectedKeys: ["5:part:pi4-dsi", "5:part:display"],
      cameraCue: { stopIndex: 1 },
    }));
    expect(screen.getByRole("button", { name: /^Fit unknown\s*5 questions$/ })).toBeVisible();
    const panels = within(screen.getByRole("group", { name: "Scene panels" }));
    const parts = panels.getByRole("button", { name: "Parts" });
    const details = panels.getByRole("button", { name: "Inspector" });
    const blockers = panels.getByRole("button", { name: "Blockers" });
    expect(parts).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Selection details" })).toBeNull();

    fireEvent.click(parts);
    const tree = within(screen.getByRole("complementary", { name: "Part tree" }));
    fireEvent.click(tree.getByRole("button", { name: "DSI FFC" }));
    expect(parts).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("fielddeck-scene").querySelector(".fd-peek"))
      .toHaveTextContent(/DSI FFC.*Physical fit · Unknown.*A.*Pi DSI port.*B.*Touch Display 2.*Pin mapping unknown/);
    const annotations = screen.getByLabelText("Scene callouts");
    expect(annotations.querySelector("[data-anchor], [data-interface-question]")).toBeNull();
    expect(annotations.querySelector('[data-question-number="1"]').parentElement).toHaveAttribute("data-dimmed", "true");
    expect(screen.getByTestId("fielddeck-scene").querySelector(".fd-peek")).toHaveTextContent("Signal voltage unknown");

    fireEvent.click(details);
    expect(parts).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    expect(inspector.getByText("Routing unknown")).toBeVisible();
    expect(inspector.getByText("Pin mapping unknown")).toBeVisible();

    fireEvent.click(blockers);
    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Selection details" })).toBeNull();
    expect(tree.getByRole("region", { name: "Blockers" })).toBeVisible();
    expect(tree.queryByRole("region", { name: "Added" })).toBeNull();
    fireEvent.click(blockers);
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
  });
});
