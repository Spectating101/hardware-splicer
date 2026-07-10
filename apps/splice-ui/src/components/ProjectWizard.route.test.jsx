import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProjectWizard from "./ProjectWizard.jsx";

vi.mock("../api.js", () => ({
  clarifyIntent: vi.fn(async () => ({ questions: [], enriched_intent: null })),
  donorBoardVision: vi.fn(),
  visionEnrichIntake: vi.fn(),
  fetchModuleCatalog: vi.fn(async () => ({
    modules: [
      { id: "esp32-devkit", label: "ESP32", pins: [] },
      { id: "dht22", label: "DHT22", pins: [] },
      { id: "usb-power-5v", label: "USB 5V", pins: [] },
    ],
  })),
}));

async function continueWizard(user) {
  const footer = document.querySelector(".wizard-footer");
  const btn = within(footer).getByRole("button", { name: /^Continue$/i });
  await user.click(btn);
}

describe("ProjectWizard route handoff", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("greenfield wizard forwards route: compose", async () => {
    const user = userEvent.setup();
    const onBuild = vi.fn();
    render(
      <ProjectWizard
        donorFixtures={[]}
        llmPolicy={{ qwen_llm_first: false }}
        onCancel={() => {}}
        onBuild={onBuild}
        building={false}
      />,
    );

    await user.type(
      screen.getByLabelText(/What do you want to build/i),
      "ESP32 soil moisture logger with OLED display board",
    );
    await continueWizard(user);
    await screen.findByRole("heading", { name: /Quick questions/i });
    await continueWizard(user);

    await screen.findByRole("heading", { name: /Choose your design path/i });
    await user.click(screen.getByRole("button", { name: /AI carrier design/i }));
    await continueWizard(user);

    await continueWizard(user); // design
    await continueWizard(user); // power

    await user.click(screen.getByRole("button", { name: /Build my project/i }));

    expect(onBuild).toHaveBeenCalledTimes(1);
    expect(onBuild.mock.calls[0][1]).toEqual({ route: "compose" });
  });

  it("salvage wizard forwards route: splice", async () => {
    const user = userEvent.setup();
    const onBuild = vi.fn();
    const fixtures = [
      {
        id: "rc_toy",
        label: "RC toy motor board",
        donor_board: { id: "rc_toy", label: "RC toy motor board" },
      },
    ];
    render(
      <ProjectWizard
        donorFixtures={fixtures}
        llmPolicy={{ qwen_llm_first: false }}
        onCancel={() => {}}
        onBuild={onBuild}
        building={false}
      />,
    );

    await user.type(
      screen.getByLabelText(/What do you want to build/i),
      "Splice RC toy motor driver into a small robot base",
    );
    await continueWizard(user);
    await screen.findByRole("heading", { name: /Quick questions/i });
    await continueWizard(user);

    await screen.findByRole("heading", { name: /Choose your design path/i });
    await user.click(screen.getByRole("button", { name: /Salvage \/ splice/i }));
    await continueWizard(user);

    await user.type(screen.getByPlaceholderText("Part name"), "drive motor");
    await continueWizard(user);

    await user.click(screen.getByRole("button", { name: /RC toy motor board/i }));
    await continueWizard(user);

    await continueWizard(user); // power

    await user.click(screen.getByRole("button", { name: /Build my project/i }));

    expect(onBuild).toHaveBeenCalled();
    expect(onBuild.mock.calls.at(-1)[1]).toEqual({ route: "splice" });
  });
});
