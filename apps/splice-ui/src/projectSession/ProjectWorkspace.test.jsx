import { useReducer } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProjectWorkspace from "./ProjectWorkspace.jsx";
import {
  ACTIONS,
  STAGES,
  createEmptySession,
  projectSessionReducer,
} from "./projectSession.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";

vi.mock("../components/DesignStudioPanel.jsx", () => ({
  default: function MockStudio({ initialPhrase, initialNodes, onOpenProject, showIntakeEmptyState }) {
    return (
      <div data-testid="mock-studio">
        <span data-testid="studio-phrase">{initialPhrase}</span>
        <span data-testid="studio-node-count">{initialNodes?.length || 0}</span>
        {showIntakeEmptyState ? <div data-testid="design-empty-state">empty</div> : null}
        <button
          type="button"
          data-testid="studio-open-project"
          onClick={() =>
            onOpenProject?.({
              composeResult: {
                out_dir: "/tmp/studio_build",
                phrase: initialPhrase || "studio phrase",
                design_quality: {
                  copper_tier: "cosmetic_preview",
                  kicad_drc_errors: 0,
                },
              },
              drc: { outDir: "/tmp/studio_build", resolved: true },
            })
          }
        >
          Continue to Verify
        </button>
      </div>
    );
  },
}));

vi.mock("../components/DesignPreviewPanel.jsx", () => ({
  default: function MockPreview({ buildDir }) {
    return <div data-testid="mock-preview">preview:{buildDir}</div>;
  },
}));

vi.mock("../components/ProjectWizard.jsx", () => ({
  default: function MockWizard({ onCompleteIntake }) {
    return (
      <div data-testid="mock-intake-wizard">
        intake
        <button
          type="button"
          data-testid="mock-commit-intake"
          onClick={() =>
            onCompleteIntake?.({
              intake: { goal: "carrier board", project_name: "carrier", mode: "greenfield" },
              goal: "carrier board",
              projectName: "carrier",
              composeMode: "canvas",
            })
          }
        >
          Continue to Design
        </button>
      </div>
    );
  },
}));

vi.mock("../api.js", () => ({
  jobBundleUrl: (id) => `/bundle/${id}`,
}));

function Harness({ initial }) {
  const [session, dispatch] = useReducer(projectSessionReducer, initial);

  return (
    <ProjectWorkspace
      session={session}
      onSetStage={(stage) => dispatch({ type: ACTIONS.SET_STAGE, stage })}
      apiOk
      llmReady={false}
      donorFixtures={[]}
      onIntakeBuild={() => {}}
      onIntakeComplete={(payload) => {
        dispatch({
          type: ACTIONS.COMMIT_INTAKE,
          intake: payload.intake,
          goal: payload.goal,
          projectName: payload.projectName,
          composeMode: payload.composeMode,
          constraints: payload.constraints,
        });
      }}
      onIntakeCancel={() => {}}
      onStudioOpenProject={({ composeResult, drc }) => {
        dispatch({
          type: ACTIONS.APPLY_STUDIO_COMPILE,
          composeResult,
          drc,
          projectPackage: {
            build_dir: composeResult.out_dir,
            info: { project_name: composeResult.phrase },
            gates: { copper_tier: "cosmetic_preview", compile_ok: true },
          },
          benchSession: { open_gate_count: 1, simulated: true },
          buildDir: composeResult.out_dir,
        });
      }}
      onGraphSync={(patch) => dispatch({ type: ACTIONS.SYNC_GRAPH, ...patch })}
      onRefreshBench={() => {}}
      onBenchSubmit={() => {}}
      onBenchCaptureSubmit={() => {}}
      onToast={() => {}}
      activeJobId={session.activeJobId}
    />
  );
}

describe("ProjectWorkspace continuity + polish", () => {
  afterEach(() => {
    cleanup();
  });

  it("keeps Design disabled until Intake commit, then Verify after compile", async () => {
    const user = userEvent.setup();
    let state = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });

    render(<Harness initial={state} />);
    expect(screen.getByTestId("project-status-header")).toBeInTheDocument();
    expect(screen.getByTestId("stage-tab-design")).toBeDisabled();
    expect(screen.getByTestId("stage-tab-verify")).toBeDisabled();

    await user.click(screen.getByTestId("mock-commit-intake"));
    expect(await screen.findByTestId("stage-design")).toBeInTheDocument();
    expect(screen.getByTestId("stage-tab-design")).not.toBeDisabled();
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("carrier board");
    expect(screen.getByTestId("design-empty-state")).toBeInTheDocument();
    expect(screen.getByTestId("stage-tab-verify")).toBeDisabled();

    // Seed nodes via re-render path: force graph then compile
    cleanup();
    state = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    state = projectSessionReducer(state, {
      type: ACTIONS.COMMIT_INTAKE,
      intake: { goal: "carrier board" },
      goal: "carrier board",
      composeMode: "canvas",
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      phrase: "carrier board",
      nodes: [{ id: "n1" }, { id: "n2" }],
      edges: [{ id: "e1" }],
      composeMode: "canvas",
    });
    state = { ...state, activeJobId: "job_stale" };

    render(<Harness initial={state} />);
    expect(screen.getByTestId("download-bundle")).toBeInTheDocument();

    await user.click(screen.getByTestId("studio-open-project"));

    expect(await screen.findByTestId("stage-verify")).toBeInTheDocument();
    expect(screen.queryByTestId("download-bundle")).not.toBeInTheDocument();
    expect(screen.getByTestId("copper-honesty")).toHaveTextContent(/not.*fabrication-ready/i);
    expect(screen.getByTestId("chip-stage")).toHaveTextContent(/Verify/i);
    expect(screen.getByTestId("project-readiness-panel")).toBeInTheDocument();
    expect(screen.getByTestId("chip-drc")).toHaveTextContent(/DRC clean/i);
    expect(screen.getByTestId("ready-design")).toHaveTextContent(/DRC clean/i);

    await user.click(screen.getByTestId("stage-tab-design"));
    expect(screen.getByTestId("stage-design")).toBeInTheDocument();
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("carrier board");
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("2");
    expect(screen.getByTestId("project-status-name")).toHaveTextContent("carrier board");
  });

  it("loaded build without Studio graph shows non-editable Design explanation", async () => {
    const user = userEvent.setup();
    let state = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      nodes: [{ id: "from_a" }],
      edges: [],
      phrase: "Project A",
    });
    state = projectSessionReducer(state, {
      type: ACTIONS.LOAD_RECENT_BUILD,
      jobId: "job_b",
      result: {
        build_dir: "/tmp/b",
        project_name: "Project B",
        goal: "Project B goal",
        project_package: {
          build_dir: "/tmp/b",
          info: { project_name: "Project B" },
          gates: { copper_tier: "cosmetic_preview", compile_ok: true },
        },
        design_quality: { copper_tier: "cosmetic_preview", kicad_drc_errors: 0 },
      },
      benchSession: { open_gate_count: 2, simulated: true, power_on_authorized: false },
    });

    expect(state.designEditable).toBe(false);
    const truth = deriveProjectTruth(state);
    expect(truth.design.state).toBe("drc_clean");
    expect(truth.copper.state).toBe("preview_only");

    render(<Harness initial={state} />);
    expect(screen.getByTestId("project-status-name")).toHaveTextContent("Project B");
    expect(screen.getByTestId("chip-evidence")).toHaveTextContent(/Simulated/i);
    expect(screen.getByTestId("project-readiness-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("readiness-hero")).not.toBeInTheDocument();
    expect(screen.queryByTestId("project-summary-bar")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("stage-tab-bench"));
    expect(screen.getByTestId("bench-evidence-banner")).toHaveTextContent(/Simulated/i);

    await user.click(screen.getByTestId("stage-tab-design"));
    expect(screen.getByTestId("design-not-editable")).toHaveTextContent(/No editable Studio graph/i);
    expect(screen.queryByTestId("mock-studio")).not.toBeInTheDocument();
  });

  it("loaded build with stored graph restores editable Design", async () => {
    const user = userEvent.setup();
    const state = projectSessionReducer(createEmptySession(), {
      type: ACTIONS.LOAD_RECENT_BUILD,
      jobId: "job_g",
      result: {
        build_dir: "/tmp/g",
        project_name: "Graph build",
        goal: "Graph goal",
        project_package: { build_dir: "/tmp/g", info: { project_name: "Graph build" } },
        studio_graph: {
          nodes: [{ id: "n1" }, { id: "n2" }],
          edges: [],
          phrase: "Graph goal",
          composeMode: "canvas",
        },
      },
    });

    render(<Harness initial={state} />);
    await user.click(screen.getByTestId("stage-tab-design"));
    expect(screen.getByTestId("mock-studio")).toBeInTheDocument();
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("2");
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("Graph goal");
  });
});
