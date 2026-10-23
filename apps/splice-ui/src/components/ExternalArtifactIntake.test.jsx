import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExternalArtifactIntake from "./ExternalArtifactIntake.jsx";
import {
  inspectExternalCircuitJson, netlistCompile, projectExternalCircuitElectricalDesign,
} from "../api.js";

vi.mock("../api.js", () => ({
  inspectExternalCircuitJson: vi.fn(),
  projectExternalCircuitElectricalDesign: vi.fn(),
  netlistCompile: vi.fn(),
}));

function upstreamFile(text, name) {
  const file = new File([text], name, { type: "application/octet-stream" });
  Object.defineProperty(file, "arrayBuffer", {
    value: async () => new TextEncoder().encode(text).buffer,
  });
  return file;
}

describe("project-first external tool intake UI", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    inspectExternalCircuitJson.mockResolvedValue({
      status: "review_required", compilable: true, authority: "proposed",
      diagnostics: { imported_component_count: 2, imported_net_count: 1, single_pin_nets: [{name:"VCC"}] },
    });
    projectExternalCircuitElectricalDesign.mockResolvedValue({
      authority: "proposed", summary: { component_count: 2, net_count: 1, erc_issue_count: 1 }, unresolved_identity: [],
    });
    netlistCompile.mockResolvedValue({ok: true, build_dir: "/tmp/example"});
  });

  it("inspects genuine external source documents through HS without an implicit compile", async () => {
    const user = userEvent.setup();
    const data = JSON.stringify([
      { type: "source_component", name: "R1", source_component_id: "a" },
      { type: "source_component", name: "C1", source_component_id: "b" },
    ]);
    render(<ExternalArtifactIntake />);
    await user.upload(screen.getByLabelText(/Choose an exported file/), upstreamFile(data, "tscircuit.json"));
    expect(await screen.findByText(/2 Circuit JSON records loaded/)).toBeTruthy();
    expect(netlistCompile).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Inspect in HS/ }));
    await waitFor(() => expect(inspectExternalCircuitJson).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(projectExternalCircuitElectricalDesign).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/HS decision: review_required/)).toBeTruthy();
    expect(netlistCompile).not.toHaveBeenCalled();
    expect(screen.getByRole("button", {name:/Explicitly compile draft/})).toBeTruthy();
  });

  it("reports upstream-vs-HS motor count disagreement rather than silently losing a motor", async () => {
    const user = userEvent.setup();
    render(<ExternalArtifactIntake session={{projectPackage:{bom:{lines:[
      {description:"DC motor",qty:1},{description:"ESP32",qty:1}
    ]}}}} />);
    await user.upload(screen.getByLabelText(/Choose an exported file/), upstreamFile(
      "Name,Qty\nDC motor,2\nESP32,1\n", "external-bom.csv"
    ));
    expect(await screen.findByText(/Quantity mismatch: DC motor/)).toBeTruthy();
    expect(screen.getByText(/Against current HS BOM: review_required/)).toBeTruthy();
    expect(netlistCompile).not.toHaveBeenCalled();
  });
  it("recognizes authentic Wokwi JSON and never mistakes it for tscircuit nor silently builds", async () => {
    const user = userEvent.setup();
    const diagram = JSON.stringify({
      version: 1, editor: "wokwi",
      parts: [
        {id:"esp",type:"wokwi-esp32-devkit-v1"},
        {id:"dht",type:"wokwi-dht22"},
      ],
      connections: [
        ["dht:VCC","esp:3V3","red",[]],
        ["dht:GND","esp:GND.1","black",[]],
        ["dht:SDA","esp:D14","green",[]],
        ["esp:TX0","$serialMonitor:RX","",[]],
      ],
    });
    render(<ExternalArtifactIntake session={{projectPackage:{bom:{lines:[
      {module_id:"esp32-devkit",qty:1},{module_id:"dht22",qty:1},
    ]}}}} />);
    await user.upload(screen.getByLabelText(/Choose an exported file/), upstreamFile(diagram,"diagram.json"));
    const report = await screen.findByTestId("wokwi-source-review");
    expect(report.textContent).toContain("2 source components, 4 connections");
    expect(report.textContent).toContain("2 functional-family candidates");
    expect(report.textContent).toContain("2 pin pairs mapped");
    expect(report.textContent).toContain("family_quantity_parity");
    expect(report.textContent).toContain("not a physical circuit");
    expect(netlistCompile).not.toHaveBeenCalled();
    expect(inspectExternalCircuitJson).not.toHaveBeenCalled();
    expect(screen.queryByRole("button",{name:/Explicitly compile draft/})).toBeNull();
  });

});
