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

vi.mock("../components/DesignStudioPanel.jsx", () => ({
  default: function MockStudio({ initialPhrase, initialNodes, onOpenProject }) {
    return (
      <div data-testid="mock-studio">
        <span data-testid="studio-phrase">{initialPhrase}</span>
        <span data-testid="studio-node-count">{initialNodes?.length || 0}</span>
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
  default: function MockWizard() {
    return <div data-testid="mock-intake-wizard">intake</div>;
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
      onIntakeCancel={() => {}}
      onStudioOpenProject={({ composeResult, drc }) => {
        dispatch({
          type: ACTIONS.APPLY_STUDIO_COMPILE,
          composeResult,
          drc,
          projectPackage: {
            build_dir: composeResult.out_dir,
            info: { project_name: composeResult.phrase },
            gates: { copper_tier: "cosmetic_preview" },
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

  it("keeps Verify unavailable before compile and unlocks after", async () => {
    const user = userEvent.setup();
    let state = projectSessionReducer(createEmptySession(), { type: ACTIONS.START_PROJECT });
    state = projectSessionReducer(state, { type: ACTIONS.SET_STAGE, stage: STAGES.design });
    state = projectSessionReducer(state, {
      type: ACTIONS.SYNC_GRAPH,
      phrase: "carrier board",
      nodes: [{ id: "n1" }, { id: "n2" }],
      edges: [{ id: "e1" }],
      composeMode: "canvas",
    });
    state = { ...state, activeJobId: "job_stale" };

    render(<Harness initial={state} />);
    expect(screen.getByTestId("project-status-header")).toBeInTheDocument();
    expect(screen.getByTestId("project-status-name")).toHaveTextContent(/carrier|Untitled|New/i);
    expect(screen.getByTestId("stage-tab-verify")).toBeDisabled();
    expect(screen.getByTestId("download-bundle")).toBeInTheDocument();

    await user.click(screen.getByTestId("studio-open-project"));

    expect(await screen.findByTestId("stage-verify")).toBeInTheDocument();
    expect(screen.queryByTestId("download-bundle")).not.toBeInTheDocument();
    expect(screen.getByTestId("copper-honesty")).toHaveTextContent(/not.*fabrication-ready/i);
    expect(screen.getByTestId("chip-stage")).toHaveTextContent(/Verify/i);

    await user.click(screen.getByTestId("stage-tab-design"));
    expect(screen.getByTestId("stage-design")).toBeInTheDocument();
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("carrier board");
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("2");
    expect(screen.getByTestId("project-status-name")).toHaveTextContent("carrier board");
  });

  it("shows simulated evidence banner on Bench and clears foreign graph on recent load", async () => {
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
          gates: { copper_tier: "cosmetic_preview" },
        },
        design_quality: { copper_tier: "cosmetic_preview", kicad_drc_errors: 0 },
      },
      benchSession: { open_gate_count: 2, simulated: true, power_on_authorized: false },
    });

    render(<Harness initial={state} />);
    expect(screen.getByTestId("project-status-name")).toHaveTextContent("Project B");
    expect(screen.getByTestId("chip-evidence")).toHaveTextContent(/Simulated/i);

    await user.click(screen.getByTestId("stage-tab-bench"));
    expect(screen.getByTestId("bench-evidence-banner")).toHaveTextContent(/Simulated/i);

    await user.click(screen.getByTestId("stage-tab-design"));
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("Project B goal");
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("0");
  });
});
