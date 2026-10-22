import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import ProjectExplorer from "./ProjectExplorer.jsx";
import { normalizeOpenBlueprintDesign, normalizeHsProjectPackage } from "./designPackage.js";

const example = {
  name: "LED test jig", summary: "A small LED tester", tags: ["BENCH"],
  parts: [
    { id: "mcu", name: "Pico", category: "mcu", domain: "electrical", qty: 1,
      unitCost: 6, pins: ["GP2", "GND"] },
    { id: "led", name: "Indicator LED", category: "actuator", domain: "electrical",
      qty: 1, unitCost: 1, pins: ["A", "K"] },
    { id: "case", name: "Test housing", category: "enclosure", domain: "mechanical",
      qty: 1, unitCost: 0, pins: [] },
  ],
  connections: [{ id: "wire-1", from: { part: "mcu", pin: "GP2" },
    to: { part: "led", pin: "A" }, net: "data", label: "GPIO" }],
  assembly: [{ part: "case", children: [{ part: "mcu" }] }],
  tools: [], assumptions: ["Check current-limiting resistor"],
  instructions: [{ id: "assembly", title: "Assemble", steps: [
    { id: "1.1", title: "Install housing", detail: "Fasten it", tools: [], parts: ["case"] },
  ] }],
};

describe("HS project explorer integration", () => {
  it("opens imported proposal tabs, part search, schematic assembly and hard evidence boundary", async () => {
    const user = userEvent.setup();
    render(<ProjectExplorer design={normalizeOpenBlueprintDesign(example)} />);
    expect(screen.getByTestId("blueprint-overview")).toHaveTextContent("Check current-limiting resistor");
    expect(screen.getByTestId("blueprint-evidence")).toHaveTextContent("not independently checked");
    expect(screen.getByText("Physical release not established")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Parts" }));
    expect(screen.getByTestId("blueprint-parts")).toHaveTextContent("Indicator LED");
    await user.type(screen.getByLabelText("Find a part"), "Pico");
    expect(screen.getByTestId("blueprint-parts")).not.toHaveTextContent("Indicator LED");

    await user.click(screen.getByRole("button", { name: "Mechanical" }));
    expect(screen.getByTestId("blueprint-mechanical")).toHaveTextContent("Test housing");
    expect(screen.getByTestId("blueprint-mechanical")).toHaveTextContent("not verified manufacturing geometry");

    await user.click(screen.getByRole("button", { name: "Build" }));
    expect(screen.getByTestId("blueprint-build")).toHaveTextContent("Install housing");

    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(screen.getByTestId("blueprint-evidence")).toHaveTextContent("not authorized");
  });

  it("shows honest topology-only fallback for HS without invented pin-level wiring", async () => {
    const user = userEvent.setup();
    const hs = normalizeHsProjectPackage({
      info: { project_name: "Donor rover", summary: "Salvage drive motors" },
      bom: { lines: [{ ref: "M1", description: "6V motor", qty: 2 }] },
      wiring: { topology_operators: [{ operator_id: "driver", inputs: ["PWM"], outputs: ["M1"] }],
        narrative_markdown: "Measure stall current before motor movement." },
      gates: { compile_ok: true },
    }, { buildDir: "/tmp/rover", designQuality: { kicad_drc_errors: 0 } });
    render(<ProjectExplorer design={hs} />);
    await user.click(screen.getByRole("button", { name: "Wiring" }));
    expect(screen.getByTestId("blueprint-wiring")).toHaveTextContent("No source-backed pin-level connection graph");
    expect(screen.getByTestId("blueprint-wiring")).toHaveTextContent("driver");
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(screen.getByTestId("blueprint-evidence")).toHaveTextContent("kicad drc reported clean");
    expect(screen.getByTestId("blueprint-evidence")).toHaveTextContent("not authorized");
  });
});
