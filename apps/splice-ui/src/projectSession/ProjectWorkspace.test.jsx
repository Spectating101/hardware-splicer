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
                design_quality: { copper_tier: "cosmetic_preview" },
              },
              drc: { outDir: "/tmp/studio_build", resolved: true },
            })
          }
        >
          Open project
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
          },
          benchSession: { open_gate_count: 1 },
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

describe("ProjectWorkspace continuity", () => {
  afterEach(() => {
    cleanup();
  });

  it("Studio compile → Verify, Design restores graph, stale bundle cleared", async () => {
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
    expect(screen.getByTestId("download-bundle")).toBeInTheDocument();
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("carrier board");

    await user.click(screen.getByTestId("studio-open-project"));

    expect(await screen.findByTestId("stage-verify")).toBeInTheDocument();
    expect(screen.queryByTestId("download-bundle")).not.toBeInTheDocument();
    expect(screen.getByTestId("mock-preview")).toHaveTextContent("/tmp/studio_build");

    await user.click(screen.getByRole("button", { name: /^Design$/i }));
    expect(screen.getByTestId("stage-design")).toBeInTheDocument();
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("carrier board");
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("2");
  });

  it("loading recent Project B clears Project A graph in the workspace", () => {
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
        project_package: { build_dir: "/tmp/b", info: { project_name: "Project B" } },
      },
    });
    state = projectSessionReducer(state, { type: ACTIONS.SET_STAGE, stage: STAGES.design });

    render(<Harness initial={state} />);
    expect(screen.getByTestId("studio-phrase")).toHaveTextContent("Project B goal");
    expect(screen.getByTestId("studio-node-count")).toHaveTextContent("0");
  });
});
