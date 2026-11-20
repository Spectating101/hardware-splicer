import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./api.js", () => ({
  fetchScenes: vi.fn(async () => []), fetchSceneManifest: vi.fn(), fetchSceneRecords: vi.fn(async () => ({ records: [] })),
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

const SNAPSHOTS = {
  1: { projectId: "plotter", projectName: "Pen plotter", mode: "greenfield", goal: "Plot A4 pages",
    intake: { goal: "Plot A4 pages", project_name: "Pen plotter" } },
  2: { projectId: "plotter", projectName: "Pen plotter r2", mode: "greenfield", goal: "Plot A3 pages",
    intake: { goal: "Plot A3 pages", project_name: "Pen plotter r2" } },
};

function respond(body, status = 200) {
  return { ok: status < 400, status, statusText: status === 404 ? "Not Found" : "OK", json: async () => body };
}

function projectRequests() {
  return fetch.mock.calls.map(([url]) => String(url).replace(/^.*(?=\/v1\/)/, ""))
    .filter((url) => /^\/v1\/projects\/[^/]+(\?|$)/.test(url));
}

describe("App URL routing", () => {
  beforeEach(() => {
    cleanup();
    vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
      const text = String(url);
      if (text.endsWith("/health")) return respond({ ok: true });
      if (options.method === "PUT") return respond({ project: { revision: 3, saved_at: "2026-11-20" } });
      const project = /\/v1\/projects\/([^/?]+)(?:\?revision=(\d+))?$/.exec(text);
      if (project) {
        if (project[1] !== "plotter") return respond({ detail: "Project not found" }, 404);
        const revision = Number(project[2] || 2);
        if (!SNAPSHOTS[revision]) return respond({ detail: "Revision not found" }, 404);
        return respond({ project: { project_id: "plotter", revision, saved_at: "2026-11-20", snapshot: SNAPSHOTS[revision] } });
      }
      if (text.endsWith("/v1/projects")) {
        return respond({ projects: [{ project_id: "plotter", name: "Pen plotter", latest_revision: 2, saved_at: "2026-11-20" }] });
      }
      return respond({ projects: [], cases: [], assessments: [], reviews: [], revisions: [] });
    }));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("reopens the project named in the URL on a fresh load", async () => {
    window.history.replaceState(null, "", "/projects/plotter");
    render(<App />);
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Pen plotter r2" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/projects/plotter");
  });

  it("opens the saved revision named by ?rev=", async () => {
    window.history.replaceState(null, "", "/projects/plotter?rev=1");
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Pen plotter" })).toBeInTheDocument();
    expect(projectRequests()).toContain("/v1/projects/plotter?revision=1");
    expect(window.location.search).toBe("?rev=1");
    expect(screen.getByText(/opened from a revision link, read-only; changes here are not saved/)).toBeInTheDocument();
    // An older revision is never written back: saving it would fork the project's history.
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(fetch.mock.calls.filter(([, options]) => options?.method === "PUT")).toEqual([]);
  });

  it("shows a not-found state for an unknown project id or revision", async () => {
    window.history.replaceState(null, "", "/projects/no-such-project");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
    expect(screen.getByText("no-such-project", { selector: "code" })).toBeInTheDocument();
    // Nothing is open, so the sidebar does not claim a project is being resumed.
    expect(screen.getByTestId("nav-project")).not.toHaveClass("active");
    expect(screen.queryByTestId("project-bench")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Back to projects" }));
    expect(await screen.findByRole("heading", { name: "Saved projects" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
    cleanup();

    window.history.replaceState(null, "", "/projects/plotter?rev=9");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
    expect(screen.getByText(/at revision 9/)).toBeInTheDocument();
  });

  it("reports a malformed revision rather than opening the latest", async () => {
    window.history.replaceState(null, "", "/projects/plotter?rev=latest");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
    expect(screen.getByText(/not a number/)).toBeInTheDocument();
    expect(projectRequests()).toEqual([]);
  });

  it("pushes history for in-app moves so Back and Forward work", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /Pen plotter/ }));
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/projects/plotter");

    await user.click(screen.getByTestId("nav-library"));
    expect(window.location.pathname).toBe("/library");
    expect(screen.queryByTestId("project-bench")).toBeNull();

    window.history.back();
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/projects/plotter");
    // Returning to the open project does not fetch it again.
    expect(projectRequests().filter((url) => url === "/v1/projects/plotter")).toHaveLength(1);

    window.history.back();
    expect(await screen.findByRole("heading", { name: "Saved projects" })).toBeInTheDocument();

    window.history.forward();
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
  });

  it("gives a project started in the app its own URL", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("home-start-project")).toBeEnabled());
    await user.click(screen.getByTestId("home-start-project"));
    expect(window.location.pathname).toBe("/projects/new");
    await user.click(screen.getByRole("button", { name: "Submit goal" }));
    expect(await screen.findByTestId("project-bench")).toBeInTheDocument();
    await waitFor(() => expect(window.location.pathname).toMatch(/^\/projects\/(?!new$)[^/]+$/));
    // The bench is already open, so its own URL does not trigger a load of an unsaved id.
    expect(screen.queryByRole("heading", { name: "Project not found" })).toBeNull();
    window.history.back();
    expect(await screen.findByTestId("new-project")).toBeInTheDocument();
  });

  it("keeps at most five saved projects in the sidebar with a way to see them all", async () => {
    const many = Array.from({ length: 7 }, (_, i) => ({ project_id: `p${i}`, name: "pen_plotter", latest_revision: 1,
      saved_at: "2026-11-20", created_at: "2026-11-19", objective: i ? `Plot sheet ${i}` : "" }));
    fetch.mockImplementation(async (url) => respond(String(url).endsWith("/health") ? { ok: true } : { projects: many }));
    window.history.replaceState(null, "", "/library");
    render(<App />);
    const all = await screen.findByTestId("sidebar-view-all");
    expect(all).toHaveTextContent("View all 7 projects");
    const saved = screen.getByText("Saved projects", { selector: ".sidebar-label" }).parentElement;
    expect(within(saved).getAllByRole("button").filter((b) => b.classList.contains("project-button"))).toHaveLength(5);
    await userEvent.click(all);
    expect(window.location.pathname).toBe("/");
    // Repeated names read the same way and carry the id tail and objective that tell them apart.
    const row = await screen.findByRole("button", { name: /^Pen plotter · p1 Plot sheet 1/ });
    expect(row).toHaveTextContent("created");
    expect(row).toHaveTextContent("Rev 1");
  });

  it("collapses the sidebar to its toggle and remembers it", async () => {
    render(<App />);
    const toggle = await screen.findByRole("button", { name: "Collapse sidebar" });
    await userEvent.click(toggle);
    expect(screen.getByTestId("app-shell")).toHaveClass("sidebar-collapsed");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute("aria-expanded", "false");
    cleanup();
    render(<App />);
    expect(screen.getByTestId("app-shell")).toHaveClass("sidebar-collapsed");
    await userEvent.click(screen.getByRole("button", { name: "Expand sidebar" }));
    expect(screen.getByTestId("app-shell")).not.toHaveClass("sidebar-collapsed");
  });

  it("opens the intake, library and advanced tools from their URLs", async () => {
    window.history.replaceState(null, "", "/projects/new");
    render(<App />);
    expect(await screen.findByTestId("new-project")).toBeInTheDocument();
    cleanup();
    window.history.replaceState(null, "", "/advanced/interface-lab");
    render(<App />);
    expect(await screen.findByTestId("interface-lab")).toBeInTheDocument();
    cleanup();
    window.history.replaceState(null, "", "/no/such/page");
    render(<App />);
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});
