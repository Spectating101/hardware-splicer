import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProjectBench from "./ProjectBench.jsx";
import NewProject from "./NewProject.jsx";
import * as api from "./digitalStudyApi.js";
import * as sceneApi from "../api.js";
import { listProjectReviews, listProjectRevisions, loadProjectReview } from "./projectReviewApi.js";

vi.mock("../api.js", () => ({
  fetchScenes: vi.fn(async () => []), fetchSceneManifest: vi.fn(), fetchSceneRecords: vi.fn(async () => ({ records: [] })),
}));
vi.mock("./digitalStudyApi.js", () => ({
  fetchChangeDossier: vi.fn(async () => ({ change_dossier: { changes: [], cite_editions: [], cite_linked: false, head_revision: 1 } })),
  fetchEngineeringPackages: vi.fn(async () => ({ packages: [] })), fetchEvidenceDelta: vi.fn(),
  fetchEngineeringRevisionDiff: vi.fn(), fetchDigitalCompare: vi.fn(),
  engineeringPackageUrl: (project, id) => `/packages/${project}/${id}`,
  fetchProjectAssurance: vi.fn(), fetchProjectMaterials: vi.fn(), fetchMaterialAssessment: vi.fn(),
  fetchPartSubstitution: vi.fn(), assessMachineRelease: vi.fn(), fetchDigitalCases: vi.fn(),
  digitalArtifactUrl: (path) => path,
}));
vi.mock("./projectReviewApi.js", () => ({
  listProjectReviews: vi.fn(), listProjectRevisions: vi.fn(async () => ({ revisions: [] })),
  loadProjectReview: vi.fn(async () => ({ review: null })), decideProjectReview: vi.fn(),
}));
// Keep the goal wizard's separate route tests; these tests exercise the new entry shell.
vi.mock("../components/ProjectWizard.jsx", () => ({ default: () => <p>Goal intake</p> }));

const session = { projectId: "bench-1", projectName: "Plotter", snapshotRevision: 4,
  intake: { owned_units: [{ unit_id: "motor-1", name: "Printer motor", source: "salvaged", known_facts: "Flange 42 mm" }] } };

beforeEach(() => {
  vi.resetAllMocks();
  api.fetchEngineeringPackages.mockResolvedValue({ packages: [] });
  api.fetchEvidenceDelta.mockResolvedValue({ base_revision: 3, candidate_revision: 4,
    evidence_delta: { affected_outputs: [], blocked_outputs: [], retained_outputs: [] } });
  sceneApi.fetchScenes.mockResolvedValue([]);
  api.fetchProjectAssurance.mockResolvedValue({ revision: 4, assurance: { claims: [], outputs: [] } });
  api.fetchProjectMaterials.mockResolvedValue({ assessments: [] });
  listProjectReviews.mockResolvedValue({ reviews: [] });
  listProjectRevisions.mockResolvedValue({ revisions: [] });
  loadProjectReview.mockResolvedValue({ review: null });
  vi.stubGlobal("matchMedia", undefined);
});
afterEach(() => vi.unstubAllGlobals());

describe("Project bench truth", () => {
  it("uses an untitled project fallback and omits an absent evidence revision", () => {
    render(<ProjectBench session={{}} />);
    expect(screen.getByRole("heading", { name: "Untitled project" })).toBeInTheDocument();
    expect(screen.getByText("Not saved yet")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Evidence" })).not.toHaveTextContent(/Revision/);
    expect(screen.getByRole("region", { name: "Parts and requirements" })).toHaveTextContent("Parts: unknown");
  });

  it("shows missing knowledge and geometry honestly and never supplies a reference model", async () => {
    render(<ProjectBench session={session} />);
    const parts = screen.getByRole("region", { name: "Parts and requirements" });
    expect(parts).toHaveTextContent("Owned unit · Origin: salvaged");
    expect(parts).toHaveTextContent("Knowledge state: unknown · Geometry: not linked");
    expect(parts).toHaveTextContent("Catalogue part: unknown");
    expect(await screen.findByText("Design view · not linked")).toBeInTheDocument();
    expect(document.querySelector("iframe, .digital-render")).toBeNull();
    const evidence = screen.getByRole("region", { name: "Evidence" });
    expect(await within(evidence).findByText(/The backend returned no blockers for this revision. Revision 4/)).toBeInTheDocument();
    expect(within(evidence).queryByText(/ready|build-ready|verified/i)).toBeNull();
    expect(screen.queryByText(/Agent proposals/)).toBeNull();
    expect(screen.getByText("References").closest("details")).not.toHaveAttribute("open");
  });

  it("renders backend authority labels and blockers verbatim without computing a verdict", async () => {
    api.fetchProjectAssurance.mockResolvedValue({ revision: 4, assurance: {
      claims: [
        { claim_id: "torque", predicate: "Torque", authority: "declared_digital_profile_only", source_id: "motor-datasheet" },
        { claim_id: "fit", predicate: "Motor fit", source_id: "drawing-3" },
      ], outputs: [{ kind: "blocker", summary: "motor torque unverified" }],
    } });
    render(<ProjectBench session={session} />);
    const evidence = screen.getByRole("region", { name: "Evidence" });
    expect(await within(evidence).findByText("declared_digital_profile_only")).toBeInTheDocument();
    expect(evidence).toHaveTextContent("Source: motor-datasheet");
    expect(evidence).toHaveTextContent("Authority: unknown");
    expect(evidence).toHaveTextContent("motor torque unverified");
    expect(evidence.textContent).not.toMatch(/\b(?:ready|build-ready)\b/i);
    expect(evidence.querySelector(".success, .pass, .status-chip--ok")).toBeNull();
    expect(within(evidence).queryByText(/no blockers/)).toBeNull();
  });

  it("marks only the outputs the backend invalidated as stale from the earlier revision", async () => {
    api.fetchProjectAssurance.mockResolvedValue({ revision: 4, assurance: {
      claims: [], outputs: [{ kind: "calculation", node_id: "torque-margin", summary: "Torque margin" }],
    } });
    api.fetchEvidenceDelta.mockResolvedValue({ base_revision: 3, candidate_revision: 4, evidence_delta: {
      affected_outputs: [{ evidence_id: "output:torque-margin", status: "invalidated", metadata: { summary: "Torque margin" } }],
      blocked_outputs: [], retained_outputs: [{ evidence_id: "output:other", status: "retained" }],
    } });
    render(<ProjectBench session={session} />);
    const delta = await screen.findByTestId("evidence-delta");
    expect(api.fetchEvidenceDelta).toHaveBeenCalledWith("bench-1", 3, 4, expect.anything());
    expect(delta).toHaveTextContent("stale · from revision 3Torque margin");
    expect(delta).toHaveTextContent("1 output retained by the backend.");
  });

  it("shows study checks the backend marked stale, the rerun failure and the package pair", async () => {
    const check = (id, passed, actual, limit, unit, revision, run) => ({ passed, actual, limit, unit, revision, run_id: run });
    api.fetchProjectAssurance.mockResolvedValue({ revision: 4, assurance: {
      claims: [], outputs: [{ kind: "check", node_id: "check:work_runtime", summary: "work_runtime" }],
    } });
    api.fetchEvidenceDelta.mockResolvedValue({ base_revision: 3, candidate_revision: 4, evidence_delta: {
      affected_outputs: [{ evidence_id: "output:check:work_runtime", status: "invalidated",
        reasons: [{ kind: "changed_dependency", ids: ["requirement:minimum_work_runtime_h"] }],
        metadata: { kind: "check", summary: "work_runtime", ...check("w", true, 3.166, 2.5, "h", 3, "run-three-abcdef"),
          rerun: check("w", false, 3.166, 3.5, "h", 4, "run-four") } }],
      blocked_outputs: [],
      retained_outputs: [{ evidence_id: "output:check:ordinary_source_margin", status: "retained",
        metadata: { kind: "check", summary: "ordinary_source_margin", ...check("o", true, .48, .3, "A", 3, "run-three"),
          rerun: check("o", true, .48, .3, "A", 4, "run-four") } }],
      study_checks: { base_revision: 3, candidate_revision: 4,
        changed_dependencies: [{ dependency_id: "requirement:minimum_work_runtime_h", before: 2.5, after: 3.5 }],
        failing_outputs: [{ node_id: "check:work_runtime", summary: "work_runtime", transition: "regressed",
          ...check("w", false, 3.166, 3.5, "h", 4, "run-four") }],
        packages: { before: { revision: 3, name: "STUDY.zip", sha256: "fddca455d5e8cf68ff", path: "/r3/STUDY.zip" },
          after: { revision: 4, name: "STUDY.zip", sha256: null, path: "/r4/STUDY.zip" } } },
    } });
    render(<ProjectBench session={session} />);
    const delta = await screen.findByTestId("evidence-delta");
    expect(delta).toHaveTextContent("Changed requirement minimum_work_runtime_h: 2.5 → 3.5");
    const stale = within(delta).getByTestId("stale-check");
    expect(stale).toHaveTextContent("stale · from revision 3work_runtime");
    expect(stale).toHaveTextContent("Revision 3 result: passed · actual 3.166 h · required ≥ 2.5 h · run run-three-ab");
    expect(stale).toHaveTextContent("Rerun in revision 4: failed · actual 3.166 h · required ≥ 3.5 h");
    expect(stale).toHaveTextContent("not counted for revision 4");
    expect(delta).toHaveTextContent("retained · from revision 3ordinary_source_margin");
    expect(delta).not.toHaveTextContent("retained by the backend");
    expect(within(delta).getByTestId("failing-checks")).toHaveTextContent("failed · revision 4 work_runtime");
    const pair = within(delta).getByTestId("package-pair");
    expect(within(pair).getByRole("link", { name: "STUDY.zip" })).toHaveAttribute("href", "/r3/STUDY.zip");
    expect(pair).toHaveTextContent("sha256 fddca455d5e8cf68");
    // A package the backend did not hash is not linked, never assumed.
    expect(pair).toHaveTextContent("Package · not linked (after)");
    expect(screen.queryByText(/ready/i)).not.toBeInTheDocument();
  });

  it("says the evidence link is not linked when the backend graph has no outputs", async () => {
    render(<ProjectBench session={session} />);
    expect(await screen.findByText("Evidence-to-revision link · not linked")).toBeInTheDocument();
    expect(api.fetchEvidenceDelta).not.toHaveBeenCalled();
  });

  it("lists revision-bound packages, marks an older one stale and keeps the objective visible", async () => {
    api.fetchEngineeringPackages.mockResolvedValue({ packages: [{ package_id: "pkg-old", source_revision: 2 }] });
    render(<ProjectBench session={{ ...session, goal: "Plot A4 drawings from salvaged steppers" }} />);
    const panel = screen.getByTestId("bench-package");
    expect(panel).toHaveTextContent("Plot A4 drawings from salvaged steppers");
    expect(await within(panel).findByText("stale · from revision 2")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /Engineering package pkg-old/ })).toHaveAttribute("href", "/packages/bench-1/pkg-old");
  });

  it("says Package · not linked when nothing has been built", async () => {
    render(<ProjectBench session={session} />);
    expect(await screen.findByText("Package · not linked")).toBeInTheDocument();
    expect(screen.getByTestId("bench-package")).toHaveTextContent("Objective · not recorded for this project");
  });

  it("does not rewrite a backend authority, even if its text contains verified", async () => {
    api.fetchProjectAssurance.mockResolvedValue({ revision: 4, assurance: {
      claims: [{ claim_id: "measured-fit", authority: "verified", source_id: "drawing" }], outputs: [],
    } });
    render(<ProjectBench session={session} />);
    expect(await screen.findByText("verified", { selector: "span" })).toBeInTheDocument();
  });

  it("does not turn a missing or failed backend response into an empty blocker assessment", async () => {
    api.fetchProjectAssurance.mockRejectedValue(new Error("Backend unavailable"));
    render(<ProjectBench session={session} />);
    expect(await screen.findByText(/Evidence: unknown. Backend unavailable/)).toBeInTheDocument();
    expect(screen.queryByText(/no blockers/)).toBeNull();
    expect(screen.getByRole("heading", { name: "Blockers" }).parentElement).toHaveTextContent("unknown");
  });

  it("loads revision-bound material records and distinguishes catalogue requirements from units", async () => {
    api.fetchProjectMaterials.mockResolvedValue({ assessments: [
      { assessment_id: "old", source_revision: 2 }, { assessment_id: "current", source_revision: 4 },
    ] });
    api.fetchMaterialAssessment.mockResolvedValue({ assessment: { source_revision: 4,
      requirements: [{ material_id: "motor", description: "Catalogue motor", catalog_part_id: 17 }],
      inventory: { lots: [{ stock_id: "stock-1", mpn: "Motor unit", catalog_part_id: 17 }] },
    } });
    api.fetchPartSubstitution.mockResolvedValue({ assessment: {
      specification: { replace_part_id: "motor-1", candidate: { part_id: "replacement", authority: "declared_contract_only" } },
    } });
    render(<ProjectBench session={{ ...session, partSubstitution: { assessment_id: "sub-1" } }} />);
    expect(await screen.findByText("Catalogue motor")).toBeInTheDocument();
    expect(api.fetchMaterialAssessment).toHaveBeenCalledWith("bench-1", "current", expect.any(AbortSignal));
    const parts = screen.getByRole("region", { name: "Parts and requirements" });
    expect(parts).toHaveTextContent("Inventory unit");
    expect(parts).toHaveTextContent("Catalogue requirement");
    expect(parts).toHaveTextContent("replacement · Authority: declared_contract_only · Source: unknown");
  });

  it("keeps proposals collapsed inside Evidence and uses the backend release blockers", async () => {
    api.assessMachineRelease.mockResolvedValue({ assessment: { blockers: [{ message: "Load evidence missing" }] } });
    listProjectReviews.mockResolvedValue({ reviews: [{ review_id: "review-1", status: "pending", note: "Motor proposal" }] });
    render(<ProjectBench session={{ ...session, machineProject: { requirements: [
      { requirement_id: "load", statement: "Carry the load", source: "intake-note", authority: "declared" },
    ] } }} />);
    const evidence = screen.getByRole("region", { name: "Evidence" });
    const disclosure = (await within(evidence).findByText("Agent proposals (1)")).closest("details");
    expect(disclosure).not.toHaveAttribute("open");
    expect(evidence).toHaveTextContent("Load evidence missing");
    expect(evidence).toHaveTextContent("Source: intake-note");
    expect(evidence).toHaveTextContent("Authority: declared");
  });

  it("switches accessible Parts / Design / Evidence tabs at the mobile breakpoint", () => {
    let change;
    const media = { matches: true, addEventListener: vi.fn((_, listener) => { change = listener; }), removeEventListener: vi.fn() };
    vi.stubGlobal("matchMedia", vi.fn(() => media));
    render(<ProjectBench session={{ ...session, snapshotRevision: 0 }} />);
    expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 899px)");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Parts", "Design", "Evidence"]);
    expect(screen.getByRole("tabpanel", { name: "Design" })).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "Parts" }));
    expect(screen.getByRole("tab", { name: "Parts" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Parts" })).toBeVisible();
    expect(screen.queryByRole("tabpanel", { name: "Design" })).toBeNull();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Parts" }), { key: "End" });
    expect(screen.getByRole("tabpanel", { name: "Evidence" })).toBeVisible();
    // A viewport change restores the simultaneous desktop panes.
    media.matches = false;
    act(() => change());
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.getByRole("region", { name: "Parts and requirements" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Design" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Evidence" })).toBeVisible();
  });
});

it("offers three list entries and submits distinct owned units, without claiming a catalogue match", () => {
  const complete = vi.fn();
  render(<NewProject online onComplete={complete} onCancel={vi.fn()} />);
  const choices = screen.getByRole("list", { name: "Project starting points" });
  expect(within(choices).getAllByRole("listitem")).toHaveLength(3);
  expect(within(choices).getAllByRole("button").map((button) => button.textContent)).toEqual([
    "Start from a goal", "Start from parts you have", "Start from a reference study",
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Start from parts you have" }));
  expect(screen.getByText(/A catalogue part describes a model/)).toBeInTheDocument();
  expect(screen.getByText(/Not saved yet. Submit an intake/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Printer stepper" } });
  fireEvent.change(screen.getByLabelText("Source"), { target: { value: "salvaged" } });
  fireEvent.change(screen.getByLabelText("Known facts"), { target: { value: "Current unknown" } });
  fireEvent.click(screen.getByRole("button", { name: "Add owned unit" }));
  fireEvent.change(screen.getAllByLabelText("Name")[1], { target: { value: "Second stepper" } });
  expect(complete).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Create project from parts" }));
  expect(complete).toHaveBeenCalledWith({ intake: expect.objectContaining({ owned_units: [
    { unit_id: "unit-1", name: "Printer stepper", source: "salvaged", known_facts: "Current unknown" },
    { unit_id: "unit-2", name: "Second stepper", source: "owned", known_facts: "" },
  ] }) });
});

describe("thresholdLabel", () => {
  it("states a minimum, a maximum, or a neutral threshold from unambiguous results only", async () => {
    const { thresholdLabel } = await import("./ProjectBench.jsx");
    expect(thresholdLabel({ actual: 0.08, limit: 0, passed: true, unit: "A" })).toBe("required ≥ 0 A");
    expect(thresholdLabel({ actual: 3.166, limit: 3.5, passed: false, unit: "h" })).toBe("required ≥ 3.5 h");
    expect(thresholdLabel({ actual: 230, limit: 250, passed: true, unit: "g" })).toBe("required ≤ 250 g");
    expect(thresholdLabel({ actual: 260, limit: 250, passed: false, unit: "g" })).toBe("required ≤ 250 g");
    expect(thresholdLabel({ actual: 2, limit: 2, passed: true, unit: "A" })).toBe("threshold 2 A");
    expect(thresholdLabel({ actual: 2, limit: 3 })).toBe("threshold 3");
  });
});
