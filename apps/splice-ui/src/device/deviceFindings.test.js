// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { indexFielddeck } from "../components/fielddeckLogic.js";
import { deviceFindings, findTargets, shortLabel } from "./deviceFindings.js";

// The real Fielddeck sidecars, as the scene routes serve them.
const repo = new URL("../../../../projects/cyberdeck-real-trial-20261020/", import.meta.url);
const read = (path) => JSON.parse(readFileSync(new URL(path, repo), "utf8"));
const sidecars = { 7: read("digital_v1/cad/parts.json"), 5: read("display_swap/parts.json") };
const compare = { base: "7", target: "5" };
const sides = { left: { value: 1.25 }, right: { value: 1.25 }, top: { value: -0.5 }, bottom: { value: 2 } };

describe("device findings from the Fielddeck records", () => {
  const labelOf = (rev) => ({ 7: "7-inch", 5: "5-inch" })[rev];
  const groups = deviceFindings({ sidecars, compare, focusPart: "display", labelOf, faceFit: { sides, aperture: "Aperture 110 × 70 mm · computed" } });
  const all = groups.flatMap((group) => group.items);

  it("groups what was chosen, how it fits and how it connects", () => {
    expect(groups.map((group) => group.title)).toEqual(["What was chosen", "How it fits", "How it connects"]);
  });

  it("states the blocked alternate with its failed checks", () => {
    const alt = all.find((item) => item.id.startsWith("alternate:"));
    expect(alt.answer).toMatch(/10-inch Touch Display 2 was blocked: enclosure fit, connector mismatch, protocol mismatch/);
    expect(alt.state).toBe("recorded");
  });

  it("reports the revision diff counts from the sidecar", () => {
    const diff = all.find((item) => item.id === "revision-diff");
    expect(diff.question).toBe("What changed from the 7-inch revision?");
    expect(diff.answer).toBe("4 parts changed, 5 added, 1 removed; 29 unchanged.");
    expect(diff.view.mode).toBe("compare");
  });

  it("answers the display fit from the CAD measurement and opens face view", () => {
    const face = all.find((item) => item.id === "face-fit");
    expect(face.state).toBe("computed");
    expect(face.answer).toBe("CAD estimate: Glass edge clear of faceplate on L/R/B · min clear 1.25 mm (L/R). Physical fit not tested.");
    expect(face.view).toMatchObject({ faceView: true, selected: "5:part:display" });
    const pending = deviceFindings({ sidecars, compare, focusPart: "display", faceFit: null })
      .flatMap((group) => group.items).find((item) => item.id === "face-fit");
    expect(pending.state).toBe("unknown");
  });

  it("names the envelope-only parts instead of implying a fit", () => {
    const rough = all.find((item) => item.id === "rough-shapes");
    expect(rough.answer).toMatch(/Nano 10000mAh 30W bank/);
    expect(rough.answer).toMatch(/not a real fit/);
  });

  it("lists every connection with its open checks, never as passed", () => {
    const links = groups.find((group) => group.id === "connects").items;
    expect(links).toHaveLength(sidecars[5].interfaces.length);
    const dsi = links.find((item) => item.id === "link:display-ribbon");
    expect(dsi.state).toBe("open");
    expect(dsi.detail).toContain("Pin mapping unknown");
    const usb = links.find((item) => item.id === "link:keyboard-usb");
    expect(usb.answer).toMatch(/Not tested on hardware/);
    for (const item of all) expect(item.state).not.toMatch(/pass|ready|ok|verified/i);
  });

  it("does not repeat interface checks as device blockers", () => {
    const reasons = all.filter((item) => item.id.startsWith("blocker:")).map((item) => item.answer);
    expect(reasons.some((text) => /pin mapping/i.test(text))).toBe(false);
  });

  it("finds parts and connections by designator or word", () => {
    const index = indexFielddeck(sidecars, compare);
    expect(findTargets(index, "5", "dsi").map((row) => row.key)).toContain("5:part:pi4-dsi");
    expect(findTargets(index, "5", "bank")[0].label).toBe("Nano 10000mAh 30W bank");
    expect(findTargets(index, "5", "")).toEqual([]);
    expect(shortLabel("Raspberry Pi Touch Display 2, 5-inch (SC1635)")).toBe("Raspberry Pi Touch Display 2");
  });

  it("points a device-level question at the connection it is about", () => {
    const gpio = all.find((item) => /GPIO extension/.test(item.answer));
    expect(gpio.question).toBe("Display GPIO power: is it rated for the job?");
    expect(gpio.view.selected).toBe("5:link:display-power");
    const routing = all.find((item) => item.question === "Do the cables route without interference?");
    expect(routing.view.selected).toBe("5:link:display-ribbon");
  });

  it("carries the exact recorded reasons, so the model's numbered pins can be matched", () => {
    const dsi = all.find((item) => item.id === "link:display-ribbon");
    expect(dsi.reasons).toEqual(sidecars[5].interfaces.find((link) => link.interface_id === "display-ribbon").open_checks);
  });
});
