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
  default: function MockWizard() {
    return <div data-testid="mock-home-intake">Project intake</div>;
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
