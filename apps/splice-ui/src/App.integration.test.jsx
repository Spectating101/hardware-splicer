import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./api.js", () => ({
  fetchHealth: vi.fn(async () => ({
    ok: true,
    version: "1.1.0",
    llm_policy: { qwen_llm_first: false },
  })),
  fetchExamples: vi.fn(async () => ({ examples: [] })),
  fetchDonorFixtures: vi.fn(async () => ({ fixtures: [] })),
  fetchJobs: vi.fn(async () => ({ jobs: [] })),
  fetchVisionCapabilities: vi.fn(async () => null),
  fetchJobResult: vi.fn(),
  benchStatus: vi.fn(async () => ({ open_gate_count: 0, power_on_authorized: false })),
  benchSubmit: vi.fn(),
  benchSubmitCapture: vi.fn(),
  renderProjectPackage: vi.fn(),
  composeAgentLoop: vi.fn(),
  fetchDesignQuality: vi.fn(),
  fetchModuleCatalog: vi.fn(async () => ({ modules: [] })),
  clarifyIntent: vi.fn(),
  donorBoardVision: vi.fn(),
  visionEnrichIntake: vi.fn(),
  jobBundleUrl: (id) => `/v1/jobs/${id}/bundle.zip`,
  buildPackageArchiveUrl: (dir) => `/v1/build-files/package-archive?build_dir=${encodeURIComponent(dir)}`,
  submitComposeJob: vi.fn(),
  submitSpliceJob: vi.fn(),
  fetchJob: vi.fn(),
}));

vi.mock("./hooks/useSpliceJob.js", () => ({
  useSpliceJob: () => ({
    job: null,
    result: null,
    error: null,
    active: false,
    elapsedSec: 0,
    stageLabel: "",
    jobKind: "splice",
    startBuild: vi.fn(),
    startCompose: vi.fn(),
    reset: vi.fn(),
    clearError: vi.fn(),
  }),
}));

vi.mock("./components/InterfaceLabPanel.jsx", () => ({
  default: function MockLab() {
    return <div data-testid="interface-lab-inner">lab</div>;
  },
}));

vi.mock("./components/PipelineVisual.jsx", () => ({
  default: function MockPipe() {
    return <div>pipeline</div>;
  },
}));

vi.mock("./components/ProjectWizard.jsx", () => ({
  default: function MockWizard({ initialGoal }) {
    return <div data-testid="mock-home-intake">Project intake
      <span data-testid="wizard-initial-goal">{initialGoal || ""}</span>
    </div>;
  },
}));

import App from "./App.jsx";
import { isAdvancedView, VIEWS } from "./nav.js";

describe("App navigation integration", () => {
  beforeEach(() => {
    cleanup();
  });

  afterEach(() => {
    cleanup();
  });

  it("Home → Start project → Intake appears", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeEnabled());
    await userEvent.click(screen.getByTestId("home-start-project"));
    expect(await screen.findByTestId("stage-intake")).toBeInTheDocument();
    expect(screen.getByText(/Project intake/i)).toBeInTheDocument();
  });

  it("starts existing intake with a home prompt, without generating an unverified project", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeEnabled());
    const prompt = screen.getByLabelText("Describe your project");
    await user.type(prompt, "Build a rover from a salvaged RC toy and ESP32");
    await user.click(screen.getByRole("button", { name: "Continue with this idea" }));
    expect(await screen.findByTestId("stage-intake")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-initial-goal")).toHaveTextContent("salvaged RC toy");
  });

  it("imports OpenBlueprint design.json locally into the read-only HS viewer", async () => {
    const user = userEvent.setup();
    render(<App />);
    const data = {
      name: "Imported bench light", summary: "OpenBlueprint proposal",
      parts: [{ id: "led", name: "LED", qty: 1, unitCost: 0.5, category: "actuator" }],
      connections: [], assembly: [], instructions: [], tags: [], tools: [], assumptions: [],
    };
    const file = new File([JSON.stringify(data)], "design.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => JSON.stringify(data) });
    await user.upload(screen.getByLabelText("Inspect an OpenBlueprint DesignPackage"), file);
    expect(await screen.findByTestId("imported-design-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("blueprint-project-explorer")).toHaveTextContent("Imported bench light");
    expect(screen.getByText("Physical release not established")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Verify" }));
    expect(screen.getByTestId("blueprint-evidence")).toHaveTextContent("not authorized");
    await user.click(screen.getByTestId("openblueprint-to-hs-intake"));
    expect(await screen.findByTestId("stage-intake")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-initial-goal")).toHaveTextContent("Imported bench light");
    expect(screen.getByTestId("wizard-initial-goal")).toHaveTextContent("Proposed, unverified parts");
  });

  it("Interface Lab is reachable only through Advanced", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("nav-advanced")).toBeInTheDocument());
    expect(screen.queryByTestId("interface-lab")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-interface-lab")).not.toBeInTheDocument();

    await userEvent.click(screen.getByTestId("nav-advanced"));
    expect(await screen.findByTestId("advanced-hub")).toBeInTheDocument();
    expect(isAdvancedView(VIEWS.lab)).toBe(true);

    await userEvent.click(screen.getByTestId("advanced-lab"));
    expect(await screen.findByTestId("interface-lab")).toBeInTheDocument();
  });

  it("does not expose Design Studio as a Home front door", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /Open Design stage/i })).not.toBeInTheDocument();
  });
});
