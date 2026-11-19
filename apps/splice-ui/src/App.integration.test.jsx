import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
  default: function MockWizard({ onCompleteIntake }) {
    return <div data-testid="mock-home-intake">Project intake<button onClick={() => onCompleteIntake({
      intake: { goal: "A pen plotter", project_name: "Plotter" },
    })}>Submit goal</button></div>;
  },
}));

import App from "./App.jsx";
import { isAdvancedView, VIEWS } from "./nav.js";

describe("App navigation integration", () => {
  beforeEach(() => {
    cleanup();
    vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
      let body = { projects: [], cases: [], assessments: [], reviews: [], revisions: [] };
      if (String(url).endsWith("/health")) body = { ok: true };
      if (options.method === "PUT") body = { project: { revision: 1, saved_at: "2026-11-18" } };
      if (String(url).includes("/engineering/assurance")) body = { revision: 1, assurance: { claims: [], outputs: [] } };
      return { ok: true, json: async () => body };
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("Home → New project shows all three entry choices and the goal intake", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeEnabled());
    await userEvent.click(screen.getByTestId("home-start-project"));
    expect(await screen.findByTestId("stage-intake")).toBeInTheDocument();
    expect(screen.getByText(/Project intake/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start from a goal" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start from parts you have" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start from a reference study" })).toBeInTheDocument();
  });

  it("does not create or persist a project when opening, editing, switching or cancelling New project", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeEnabled());
    await user.click(screen.getByTestId("home-start-project"));
    await user.click(screen.getByRole("button", { name: "Start from parts you have" }));
    await user.type(screen.getByLabelText("Name"), "Salvaged motor");
    await user.click(screen.getByRole("button", { name: "Start from a reference study" }));
    await user.click(screen.getByRole("button", { name: "Cancel", exact: true }));
    await user.click(screen.getByTestId("home-start-project"));
    // The autosave debounce is 700 ms: opening twice must never write Intake R1.
    await new Promise((resolve) => setTimeout(resolve, 800));
    expect(fetch.mock.calls.filter(([, options]) => options?.method && options.method !== "GET")).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Submit goal" }));
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
    await waitFor(() => expect(fetch.mock.calls.some(([url, options]) =>
      String(url).endsWith("/snapshot") && options?.method === "PUT")).toBe(true), { timeout: 2000 });
  });

  it("opens on Projects and keeps the reference viewers in the design library", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.queryByTestId("nav-sortcell")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Browse design library" }));
    expect(screen.getByRole("heading", { name: "Choose a design to study" })).toBeInTheDocument();
    expect(screen.getByTestId("nav-complete-assembly")).toBeEnabled();
    expect(screen.getByTestId("nav-sortcell")).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Projects", exact: true }));
    expect(screen.getByRole("heading", { name: "Saved projects" })).toBeInTheDocument();
  });

  it.each([null, "invalid-date"])("uses UI fallbacks for missing project metadata with save time %s", async (savedAt) => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ projects: [
      { project_id: "untitled", saved_at: savedAt },
    ] }) });
    render(<App />);
    const project = await screen.findByRole("button", { name: "Untitled project Not saved" });
    expect(project).not.toHaveTextContent(/unknown|Rev/);
    expect(project.querySelector(".project-stage")).toBeNull();
    await userEvent.click(screen.getByTestId("nav-advanced"));
    const savedProjects = screen.getByText("Saved projects", { selector: ".sidebar-label" }).parentElement;
    const savedProject = within(savedProjects).getByRole("button", { name: "Untitled project" });
    expect(savedProject).toHaveAttribute("title", "Not saved");
    expect(savedProject).not.toHaveTextContent(/unknown|undefined|null/);
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
