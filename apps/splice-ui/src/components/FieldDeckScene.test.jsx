import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FieldDeckScene, { EvidenceRows } from "./FieldDeckScene.jsx";
import {
  classifyPart, evidenceCells, formatEvidenceSource, formatEvidenceValue, indexFielddeck,
  rowForNode, rowsForMode, selectedPartKeys,
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
  beforeEach(() => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn(),
    })));
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
    stageMock.load.mockResolvedValue(Object.fromEntries(
      Object.entries(sides).map(([rev, sidecar]) => [rev, { sidecar, gltf: {} }]),
    ));
    let callbacks;
    const update = vi.fn();
    stageMock.create.mockImplementation((_host, _assets, index, handlers) => {
      callbacks = handlers;
      handlers.onFrame();
      return {
        linked: new Set([...index.byKey.values()].filter(({ part }) => part).map(({ key }) => key)),
        update, dispose: vi.fn(),
      };
    });
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
    expect(screen.getByRole("slider", { name: "Explode" })).toHaveValue("0.55");
    expect(update).toHaveBeenLastCalledWith(expect.objectContaining({
      selectedKeys: ["5:part:pi4-dsi", "5:part:display"],
    }));
    expect(screen.getByText("No physical validation performed")).toBeVisible();
    expect(screen.getByText("1 blocker")).toBeVisible();
    expect(screen.getByTestId("fielddeck-scene")).not.toHaveTextContent(/\bready\b/i);
  });
});
