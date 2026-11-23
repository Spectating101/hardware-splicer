// Switching projects must never show the previous project's findings under the new title.
import { join } from "node:path";
import { readFileSync } from "node:fs";
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const fixture = (name) => JSON.parse(readFileSync(join(process.cwd(), "src/device/__fixtures__", `${name}.json`), "utf8"));
const manifests = {
  "esp32-servo-board": { title: "ESP32 servo controller board", geometry_status: "available", revisions: [{ id: "a", label: "Board A", board: "examples/x.kicad_pcb" }] },
  "drone-build": { title: "Holybro X500 V2 frame", geometry_status: "unavailable", geometry_note: "not geometrically validated", revisions: [{ id: "v1", label: "v1" }] },
};

vi.mock("../api", () => ({
  fetchSceneManifest: vi.fn(async (id) => manifests[id]),
  fetchSceneEvidence: vi.fn(async (id) => (id === "drone-build" ? fixture("evidence-drone-build") : { records: [] })),
  fetchSceneKicad: vi.fn(async () => fixture("kicad-esp32-board")),
  fetchSceneFit: vi.fn(async () => { throw new Error("no fit in this test"); }),
  fetchSceneDecisions: vi.fn(async () => ({})),
  postSceneDecision: vi.fn(),
}));
vi.mock("../components/FieldDeckScene.jsx", () => ({ default: () => null }));

import DeviceWorkspace from "./DeviceWorkspace.jsx";

describe("switching projects", () => {
  it("drops the previous project's KiCad findings", async () => {
    const view = render(<DeviceWorkspace sceneId="esp32-servo-board" />);
    await screen.findByText("ESP32 servo controller board");
    await act(async () => { view.rerender(<DeviceWorkspace sceneId="drone-build" />); });
    await screen.findByText("Holybro X500 V2 frame");
    await screen.findByText("Why that strategy?");
    expect(screen.queryByText(/KiCad/)).toBeNull();
    expect(screen.queryByText(/Shorts between nets/)).toBeNull();
  });
});
