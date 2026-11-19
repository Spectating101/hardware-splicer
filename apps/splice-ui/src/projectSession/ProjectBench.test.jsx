import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ProjectBench from "./ProjectBench.jsx";
import NewProject from "./NewProject.jsx";
import * as api from "./digitalStudyApi.js";
import { listProjectReviews, listProjectRevisions, loadProjectReview } from "./projectReviewApi.js";

vi.mock("./digitalStudyApi.js", () => ({
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
    expect(screen.getByText("No reference study yet")).toBeInTheDocument();
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
