import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Bench from "./Bench.jsx";

const TOOLS = [{
  name: "hs_trace_current",
  description: "Check a routed board's narrowest track per net against a current.",
  input_schema: { type: "object", properties: { pcb: { type: "string" }, net_currents_a: { type: "object" } }, required: ["pcb", "net_currents_a"] },
}];
const REGISTRY = { tool: "hs_external_tools", ok: true, result: { tools: [
  { role: "routing", name: "KiCadRoutingTools", licence: "MIT", how: "separate program", status: "integrated", measured: "3 of 3 boards connected", record: "examples/r.json", source: "https://github.com/drandyhaas/KiCadRoutingTools" },
] } };
const SPINE = {
  gates: [11],
  run: { name: "HS-BUS-A", revision: "A", kicad: "9.0.2", record: "projects/hs-bus-a/verification.json", not_checked: ["Nothing has been fabricated or powered"], renders: [], claim_boundary: "Software checks only." },
  steps: [
    { n: 8, key: "krt", title: "Route fallback", runs: ["KiCadRoutingTools"], gate: false, stops_on: null, tool: "hs_component_board", run: { line: "not run on this build", outcome: "not_run" } },
    { n: 11, key: "drc", title: "DRC + parity", runs: ["KiCad"], gate: true, stops_on: "any DRC error", tool: "hs_component_board", run: { line: "0 errors · 2 warnings", outcome: "clean" } },
  ],
};
const RUN = { tool: "hs_trace_current", ok: false, summary: "4 nets checked; hottest /VIN +30 C at 7.5 A", problems: ["/VIN: 2.5 mm rises 30 C"], result: { nets: [] }, sources: [], claim_boundary: "Chart fit, not measured." };

function respond(body) {
  return Promise.resolve({ ok: true, status: 200, statusText: "OK", json: () => Promise.resolve(body) });
}

describe("Workbench", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((url, init) => {
      if (url.endsWith("/v1/toolbelt/tools")) return respond(TOOLS);
      if (url.endsWith("/v1/toolbelt/hs_external_tools")) return respond(REGISTRY);
      if (url.endsWith("/v1/bench/spine")) return respond(SPINE);
      if (url.endsWith("/v1/bench/measures")) return respond({});
      if (url.endsWith("/v1/toolbelt/hs_trace_current") && init?.method === "POST") return respond(RUN);
      return Promise.reject(new Error(`unexpected ${url}`));
    }));
  });
  afterEach(() => { vi.unstubAllGlobals(); window.localStorage.clear(); });

  it("lays the recorded run over the spine and reports a step that did not run as not run", async () => {
    render(<Bench />);
    expect(await screen.findByText("0 errors · 2 warnings", { selector: ".wb-step-line" })).toBeInTheDocument();
    expect(screen.getByText("not run on this build", { selector: ".wb-step-line" })).toBeInTheDocument();
    expect(screen.getByText("Nothing has been fabricated or powered")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Engine connected");
  });

  it("opens an outside tool from a spine step with its licence and measurement", async () => {
    const user = userEvent.setup();
    render(<Bench />);
    await user.click(await screen.findByRole("button", { name: /Route fallback/, pressed: false }));
    await user.click(within(screen.getByRole("complementary", { name: "Inspector" })).getByRole("button", { name: /KiCadRoutingTools/ }));
    const inspector = screen.getByRole("complementary", { name: "Inspector" });
    expect(inspector).toHaveTextContent("MIT");
    expect(inspector).toHaveTextContent("3 of 3 boards connected");
  });

  it("refuses to run with a required input missing, then shows the engine's problems verbatim", async () => {
    const user = userEvent.setup();
    render(<Bench />);
    await screen.findByText(/Engine connected/, { selector: ".wb-log-text" });
    await user.keyboard("{Control>}k{/Control}");
    await user.keyboard("trace");
    await user.keyboard("{Enter}");
    await user.click(screen.getByRole("button", { name: /^Run$/ }));
    expect(screen.getAllByText("Required")).toHaveLength(2);
    await user.type(screen.getByLabelText(/^pcb/), "b.kicad_pcb");
    await user.click(screen.getByLabelText(/^net_currents_a/));
    await user.paste('{"/VIN": 7.5}');
    await user.click(screen.getByRole("button", { name: /^Run$/ }));
    expect(await screen.findByText("/VIN: 2.5 mm rises 30 C")).toBeInTheDocument();
    expect(screen.getByText("problems reported", { selector: ".wb-runbar .wb-status" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Console" })).getByText(/hottest \/VIN/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(/build-ready|\bready\b/i);
  });
});
