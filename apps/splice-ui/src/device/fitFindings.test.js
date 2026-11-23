// @vitest-environment node
// Measured-fit findings on real fit-engine output (src/hardware_splicer/scene_fit.py run on each
// project's committed model), across four different devices.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { fitFindings } from "./deviceFindings.js";

const here = (path) => new URL(path, import.meta.url);
const repo = (path) => new URL(`../../../../${path}`, import.meta.url);
const json = (url) => JSON.parse(readFileSync(url, "utf8"));
const fixture = (name) => json(here(`./__fixtures__/fit-${name}.json`));

function items(fit, sidecarPath, revision) {
  return fitFindings(fit, { sidecar: json(repo(sidecarPath)), revision, labelOf: (rev) => `${rev}-rev` })
    .flatMap((group) => group.items);
}

describe("measured fit findings", () => {
  it("Fielddeck 7-inch: no clash, the open display mesh named, and the display seated on its trays", () => {
    const fit = fixture("fielddeck-7");
    const all = items(fit, "projects/cyberdeck-real-trial-20261020/digital_v1/cad/parts.json", "7");
    const clash = all.find((item) => item.id === "fit:no-clash");
    expect(clash.state).toBe("unknown");
    expect(clash.answer).toMatch(/open mesh, so its overlap was not computed/);
    // Exact point-to-surface refinement: the display rests on the rear trays (sampling alone read 0.075 mm).
    const seated = fit.pairs.find((row) => row.a === "tray-rear-right" && row.b === "display");
    expect(seated).toMatchObject({ kind: "touching", gap_mm: 0 });
    const touching = all.find((item) => item.id === "fit:touching");
    expect(touching.view).toMatchObject({ explode: 0 });
    // The whole set of touching pairs is highlighted, not only the first pair.
    const touchingParts = new Set(fit.pairs.filter((row) => row.kind === "touching").flatMap((row) => [row.a, row.b]));
    expect(touching.view.also.length + 1).toBe(Math.min(40, touchingParts.size));
  });

  it("SPI flash board: a footprint seated on the board is touching, not a tight gap", () => {
    const fit = fixture("spi-board");
    expect(fit.pairs.find((row) => row.a === "c3" && row.b === "board")).toMatchObject({ kind: "touching", gap_mm: 0 });
    const all = items(fit, "projects/spi-flash-adapter-board/parts.json", "a");
    const grouped = all.find((item) => item.id === "fit:tight-stand-in");
    expect(grouped.answer).toMatch(/^9 pairs under 1 mm apart where at least one part is an envelope or unknown shape/);
    expect(all.filter((item) => item.id.startsWith("fit:tight:"))).toHaveLength(0);
  });

  it("Fielddeck 7-inch: a repeated gap is grouped as one seam, not twenty alarms", () => {
    const all = items(fixture("fielddeck-7"), "projects/cyberdeck-real-trial-20261020/digital_v1/cad/parts.json", "7");
    const seam = all.find((item) => item.id === "fit:tight:0.30");
    expect(seam.answer).toMatch(/pairs at most 0\.30 mm apart, a repeated gap: possibly a designed seam \(intent not recorded\)/);
    expect(seam.detail.at(-1)).toMatch(/^and \d+ more$/);
  });

  it("Ender-3: overlaps between reference envelopes are stand-in results, never collisions", () => {
    const all = items(fixture("ender3"), "projects/ender3-penplotter-digital/exports/parts.json", "v1");
    expect(all.some((item) => item.state === "clash")).toBe(false);
    const standIn = all.find((item) => item.id === "fit:stand-in-overlaps");
    expect(standIn.answer).toMatch(/^13 pairs of envelope or unknown shapes overlap/);
    expect(standIn.answer).toMatch(/not that real parts collide/);
    expect(all.find((item) => item.id === "fit:no-clash").state).toBe("computed");
  });

  it("HS-3G-B drone: the measured size agrees with the study's own model bounds", () => {
    const fit = fixture("hs3g-b");
    const model = json(repo("examples/drone_proving_ground/digital/reference/model.json"));
    const studyMm = [0, 1, 2].map((axis) => (model.bounds_m[1][axis] - model.bounds_m[0][axis]) * 1000);
    fit.size_mm.forEach((value, axis) => expect(Math.abs(value - studyMm[axis])).toBeLessThan(0.5));
    const size = items(fit, "projects/hs3g-b-drone/parts.json", "b").find((item) => item.id === "fit:size");
    expect(size.answer).toBe("155.5 × 163.6 × 74.0 mm overall, as modelled in the b-rev revision.");
  });

  it("ESP32 board: footprints seated on the board read as touching, and every result names its basis", () => {
    const all = items(fixture("esp32-board"), "projects/esp32-servo-board/parts.json", "a");
    const touching = all.find((item) => item.id === "fit:touching");
    expect(touching.answer).toMatch(/stacked, seated or fastened parts/);
    for (const item of all) {
      expect(item.basis).toBeTruthy();
      expect(item.state).not.toMatch(/pass|ready|ok|verified/i);
    }
  });

  it("a real collision is named with its volume and both parts highlighted", () => {
    const fit = { ...fixture("esp32-board"), pairs: [{ a: "u1", b: "c1", kind: "overlap", basis: ["custom", "custom"],
      stand_in: false, gap_mm: 0, precision_mm: 0, overlap_mm3: 12.34, overlap_computed: true }] };
    const clash = items(fit, "projects/esp32-servo-board/parts.json", "a").find((item) => item.state === "clash");
    expect(clash.answer).toBe("Yes in the CAD model: they overlap by 12.3 mm³.");
    expect(clash.view.also).toEqual(["a:part:c1"]);
  });

  it("no report, no findings", () => {
    expect(fitFindings(null, {})).toEqual([]);
  });
});
