// @vitest-environment node
// KiCad and evidence findings on real server output (GET /kicad and GET /evidence) for four devices.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { evidenceFindings, kicadFindings } from "./deviceFindings.js";

const fixture = (name) => JSON.parse(readFileSync(new URL(`./__fixtures__/${name}.json`, import.meta.url), "utf8"));
const flat = (groups) => groups.flatMap((group) => group.items);

describe("KiCad findings", () => {
  it("ESP32 board: DRC failures are named, counted and traced to parts", () => {
    const report = fixture("kicad-esp32-board");
    const groups = kicadFindings(report, { revision: "a" });
    expect(groups[0].title).toBe("Electrical checks (KiCad)");
    const items = flat(groups);
    const summary = items.find((item) => item.id === "kicad:drc");
    expect(summary.state).toBe("failing");
    expect(summary.answer).toBe(`No: ${report.drc.counts.error} errors and ${report.drc.counts.warning} warnings from KiCad ${report.drc.kicad_version}.`);
    const shorts = items.find((item) => item.id === "kicad:drc:shorting_items");
    expect(items.indexOf(shorts)).toBe(1); // the most serious class leads
    expect(shorts.answer).toMatch(/^14 violations, 14 of them errors, at /);
    expect(shorts.view.selected).toMatch(/^a:part:[a-z]+\d+$/);
  });

  it("SPI board: a clean DRC and ERC read as checked, with the non-claim", () => {
    const items = flat(kicadFindings(fixture("kicad-spi-board"), { revision: "a" }));
    expect(items.map((item) => item.id)).toEqual(["kicad:drc", "kicad:erc"]);
    for (const item of items) {
      expect(item.state).toBe("checked");
      expect(item.answer).toMatch(/no (DRC|ERC) violations\. A CAD check, not physical proof\./);
    }
  });
});

describe("evidence findings", () => {
  it("drone-build: every strategy option with its known cost and gaps, and the recorded reason", () => {
    const items = flat(evidenceFindings(fixture("evidence-drone-build").records, { revision: "v1" }));
    const options = items.filter((item) => item.id.startsWith("strategy:") && item.id !== "strategy:decision");
    expect(options).toHaveLength(4);
    expect(options[0].answer).toMatch(/^\$579\.00 known, incomplete: 4 items not costed\. Chosen as the first reference\.$/);
    expect(options.find((item) => item.id === "strategy:multi_donor_custom").answer).toMatch(/^No verified cost.*Chosen as the custom splicing investigation\.$/);
    const why = items.find((item) => item.id === "strategy:decision");
    expect(why.detail).toContain("Procurement approved: no");
  });

  it("HS-3G-B: simulation results say simulated, never flown", () => {
    const items = flat(evidenceFindings(fixture("evidence-hs3g-b-drone").records, { revision: "b" }));
    const missions = items.find((item) => item.id === "simulation:missions");
    expect(missions.state).toBe("simulated");
    expect(missions.answer).toMatch(/^3 of 3 scenarios behaved as expected in the simulation.*Not a physical flight; flight is not authorized\.$/);
    expect(missions.detail.find((line) => line.startsWith("motor failure"))).toMatch(/fault detected/);
  });

  it("SPI board: receipt, external tool and cost, each with its source", () => {
    const records = fixture("evidence-spi-flash-adapter-board").records;
    const partIds = new Set(["u1", "u2", "u3", "c1", "c2", "r4", "tp3"]);
    const items = flat(evidenceFindings(records, { revision: "a", partIds }));
    const receipt = items.find((item) => item.id === "receipt:checks");
    expect(receipt.answer).toMatch(/fabrication and power-on not authorized\.$/);
    expect(receipt.detail).toContain("This receipt does not authorize fabrication or power-on.");
    const tool = items.find((item) => item.id === "tool:tipoLi5890/akcli");
    expect(tool.answer).toMatch(/^tipoLi5890\/akcli at 2126c32 \(MIT\) ran on this design/);
    expect(tool.view.selected).toMatch(/^a:part:/);
    expect(items.find((item) => item.id === "tool:not-run:0x12net/kdif").answer).toMatch(/not executed/);
    expect(items.find((item) => item.id.startsWith("bom:")).answer).toMatch(/^\$[\d,.]+ known across/);
    for (const item of items) expect(item.basis).toBeTruthy();
  });

  it("an unreadable record is shown as unknown, not dropped", () => {
    const items = flat(evidenceFindings([{ kind: "bom_csv", label: "BOM", source: "x.csv", error: "Evidence record not found" }], { revision: "a" }));
    expect(items[0]).toMatchObject({ state: "unknown", answer: "Not readable: Evidence record not found." });
  });
});

describe("grouped KiCad findings", () => {
  it("highlight every part and net the group's violations touch, not only the first", () => {
    const report = fixture("kicad-esp32-board");
    const shorts = flat(kicadFindings(report, { revision: "a" })).find((item) => item.id === "kicad:drc:shorting_items");
    const rows = report.drc.violations.filter((row) => row.type === "shorting_items");
    const touched = new Set(rows.flatMap((row) => [...(row.part_ids ?? []), ...(row.net_ids ?? [])]));
    const highlighted = [shorts.view.selected, ...shorts.view.also];
    expect(highlighted).toHaveLength(Math.min(40, touched.size));
    expect(highlighted.length).toBeGreaterThan((rows[0].part_ids ?? []).length + (rows[0].net_ids ?? []).length);
  });
});
