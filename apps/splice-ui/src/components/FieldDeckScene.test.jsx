import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FieldDeckScene, { EvidenceRows } from "./FieldDeckScene.jsx";
import {
  FIELDDECK_NARROW, classifyPart, evidenceCells, formatEvidenceSource, formatEvidenceValue,
  indexFielddeck, placeCallouts, rowForNode, rowsForMode, selectedPartKeys, toggleFielddeckSheet,
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
const sides = {
  "7": {
    parts: [part("display", "PANEL_7", "vendor_step", { label: "7-inch panel" })],
    blockers: [],
    interfaces: [],
  },
  "5": {
    parts: [
      part("display", "Panel 5", "vendor_step", { label: "5-inch panel" }),
      part("pi4-dsi", "pi4_dsi", "envelope", { label: "Pi DSI port" }),
      part("tray", "Tray", "custom", { label: "Rear tray" }),
    ],
    blockers: [{ part_id: "display", reason: "display lug thread/engagement nominal only" }],
    interfaces: [{
      interface_id: "display-ribbon", label: "DSI FFC", from_part_id: "pi4-dsi", to_part_id: "display",
      open_checks: ["pin_mapping_unknown", "signal_voltage_unknown"],
    }],
    revision_diff: {
      status: "available",
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
        update, dispose: vi.fn(),
      };
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("renders unknown values and preserves known fields and sources", () => {
    render(<EvidenceRows evidence={[
      { field: "pin_mapping", value: false, state: "unknown", source: null },
      { field: "documented_power_w", value: 1.4, state: "datasheet", source: "brief.pdf" },
    ]} />);
    const unknown = screen.getByText("pin_mapping").parentElement;
    expect(unknown.querySelector(".fd-evidence-value")).toHaveTextContent(/^unknown$/);
    expect(unknown.querySelector(".fd-evidence-source")).toHaveTextContent(/^unknown$/);
    expect(screen.getByText("1.4 W")).toBeVisible();
    expect(screen.getByText("datasheet")).toBeVisible();
    expect(screen.getByRole("link", { name: "brief.pdf" })).toBeVisible();
  });

  it("syncs picks and interface selection with the tree and shows no readiness claim", async () => {
    render(<FieldDeckScene />);
    const tree = within(screen.getByRole("complementary", { name: "Part tree" }));
    const assembly = tree.getByRole("button", { name: "Assembly" });
    expect(assembly).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Selection details" })).toBeNull();
    fireEvent.click(assembly);
    const tray = await tree.findByRole("button", { name: "Rear tray" });
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    act(() => callbacks.onPick("5:part:tray"));
    expect(tray).toHaveAttribute("aria-pressed", "true");
    expect(inspector.getByText("geometry changed")).toBeVisible();
    fireEvent.click(tree.getByRole("button", { name: "DSI FFC" }));
    expect(inspector.getByText("pin_mapping_unknown")).toBeVisible();
    expect(inspector.getByText("signal_voltage_unknown")).toBeVisible();
    expect(screen.getByRole("slider", { name: "Explode" })).toHaveValue("0.6");
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({
      selectedKeys: ["5:part:pi4-dsi", "5:part:display"],
    }));
    expect(screen.getByText("No physical validation performed")).toBeVisible();
    expect(screen.getByText("1 blocker")).toBeVisible();
    expect(screen.getByTestId("fielddeck-scene")).not.toHaveTextContent(/\bready\b/i);
    act(() => callbacks.onCalloutLayout(["5:link:display-ribbon"]));
    expect(within(inspector.getByLabelText("Scene callouts")).getByText("DSI FFC")).toBeVisible();
  });

  it("opens only one narrow sheet and keeps callouts inside Details", async () => {
    narrow = true;
    render(<FieldDeckScene />);
    const parts = await screen.findByRole("button", { name: "Parts" });
    const details = screen.getByRole("button", { name: "Details" });
    expect(parts).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Selection details" })).toBeNull();

    fireEvent.click(parts);
    const tree = within(screen.getByRole("complementary", { name: "Part tree" }));
    fireEvent.click(tree.getByRole("button", { name: "DSI FFC" }));
    expect(parts).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByLabelText("Scene callouts")).toBeNull();

    fireEvent.click(details);
    expect(parts).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveAttribute("aria-expanded", "true");
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
    const inspector = within(screen.getByRole("complementary", { name: "Selection details" }));
    expect(within(inspector.getByLabelText("Scene callouts")).getByText("DSI FFC")).toBeVisible();
    expect(inspector.getByText("pin_mapping_unknown")).toBeVisible();
    expect(screen.getByTestId("fielddeck-scene").querySelector("[data-anchor]")).toBeNull();

    fireEvent.click(parts);
    expect(details).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("complementary", { name: "Selection details" })).toBeNull();
    fireEvent.click(parts);
    expect(screen.queryByRole("complementary", { name: "Part tree" })).toBeNull();
  });
});
