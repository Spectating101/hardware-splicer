// The record a question is about, drawn from real evidence records served for two devices.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { evidenceFindings } from "./deviceFindings.js";
import { EvidenceCanvas } from "./EvidenceCanvas.jsx";

const fixture = (name) => JSON.parse(readFileSync(join(process.cwd(), "src/device/__fixtures__", `${name}.json`), "utf8"));
const item = (name, id) => evidenceFindings(fixture(name).records, { revision: "b" }).flatMap((group) => group.items).find((row) => row.id === id);

describe("evidence canvas", () => {
  it("compares every strategy option with its known cost and what it was chosen as", () => {
    const why = item("evidence-drone-build", "strategy:decision");
    render(<EvidenceCanvas canvas={why.canvas} onClose={() => {}} />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(1 + why.canvas.record.options.length);
    expect(within(table).getByText("$579.00")).toBeTruthy();
    expect(within(table).getAllByText(/not costed/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Procurement approved: no/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b(passed|approved: yes|ready)\b/i);
  });

  it("lists each simulated scenario and never says it flew", () => {
    const missions = item("evidence-hs3g-b-drone", "simulation:missions");
    expect(missions.answer).toMatch(/including a motor failure that was detected/);
    render(<EvidenceCanvas canvas={missions.canvas} onClose={() => {}} />);
    expect(screen.getAllByRole("row")).toHaveLength(1 + missions.canvas.record.scenarios.length);
    expect(screen.getByText(/motor failure/)).toBeTruthy();
    expect(screen.getByText(/nothing here has flown/)).toBeTruthy();
  });

  it("only claims a detected motor failure when the record shows one", () => {
    const records = fixture("evidence-hs3g-b-drone").records.map((record) => ({
      ...record, scenarios: record.scenarios?.map((row) => ({ ...row, metrics: { ...row.metrics, fault_detected: false } })) }));
    const missions = evidenceFindings(records, { revision: "b" }).flatMap((group) => group.items).find((row) => row.id === "simulation:missions");
    expect(missions.answer).not.toMatch(/motor failure/);
  });
});
