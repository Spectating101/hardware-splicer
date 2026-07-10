import DesignPreviewPanel from "../components/DesignPreviewPanel.jsx";
import DesignStudioPanel from "../components/DesignStudioPanel.jsx";
import ProjectSummaryBar from "../components/ProjectSummaryBar.jsx";
import ReadinessHero from "../components/ReadinessHero.jsx";
import TabNav from "../components/TabNav.jsx";
import {
  BomPanel,
  BenchPanel,
  GatesPanel,
  InfoPanel,
  InstructionsPanel,
  WiringPanel,
} from "../components/ProjectPanels.jsx";
import { jobBundleUrl } from "../api.js";
import {
  STAGE_LABELS,
  STAGE_ORDER,
  STAGES,
  canReturnToDesign,
  sessionHasPackage,
} from "./projectSession.js";

const STAGE_TABS = STAGE_ORDER.map((id) => ({
  id,
  label: STAGE_LABELS[id],
  highlight: id === STAGES.design || id === STAGES.verify,
}));

/**
 * Project workspace shell — stages wrap existing panels.
 * Does not introduce a second compile path.
 */
export default function ProjectWorkspace({
  session,
  onSetStage,
  apiOk,
  llmReady,
  onStudioOpenProject,
  onGraphSync,
  onRefreshBench,
  onBenchSubmit,
  onBenchCaptureSubmit,
  onToast,
  activeJobId,
}) {
  const pkg = session.projectPackage;
  const buildDir = session.buildDir || pkg?.build_dir || null;
  const displayResult = session.displayResult;
  const stage = session.currentStage || STAGES.design;
  const hasPkg = sessionHasPackage(session);

  const openGateCount =
    session.benchSession?.open_gate_count ?? (session.benchSession?.open_gates || []).length;

  const badges = {
    [STAGES.bench]: openGateCount,
  };

  return (
    <div className="project-workspace">
      <header className="project-header">
        <div className="project-header-text">
          <p className="eyebrow">Project workspace</p>
          <h1>{session.projectName || pkg?.info?.project_name || "Untitled project"}</h1>
          <p className="muted">{session.goal || pkg?.info?.goal || "Greenfield design in progress"}</p>
        </div>
        <div className="project-header-actions">
          {activeJobId && (
            <>
              <button
                type="button"
                className="ghost button-link"
                onClick={() => {
                  navigator.clipboard?.writeText(jobBundleUrl(activeJobId));
                  onToast?.("Share link copied — download bundle for reviewers");
                }}
              >
                Share bundle link
              </button>
              <a className="secondary button-link" href={jobBundleUrl(activeJobId)} download>
                ↓ Download zip
              </a>
            </>
          )}
        </div>
      </header>

      <TabNav tabs={STAGE_TABS} activeId={stage} onChange={onSetStage} badges={badges} />

      {hasPkg && stage !== STAGES.design && stage !== STAGES.intake && (
        <>
          <ReadinessHero
            pkg={pkg}
            benchSession={session.benchSession}
            onGoDesign={() => onSetStage(STAGES.verify)}
            onGoBench={() => onSetStage(STAGES.bench)}
            onGoGates={() => onSetStage(STAGES.bench)}
          />
          <ProjectSummaryBar
            pkg={pkg}
            benchSession={session.benchSession}
            onGoBench={() => onSetStage(STAGES.bench)}
            onGoDesign={() => onSetStage(STAGES.verify)}
          />
        </>
      )}

      <div className="workspace-stage">
        {stage === STAGES.intake && (
          <section className="card">
            <h2>Intake</h2>
            <p className="muted">
              Project intent and constraints. Use <strong>New project</strong> for the full wizard
              (greenfield or salvage). Design Studio can also start from a phrase on the Design stage.
            </p>
            <dl className="meta-grid">
              <div>
                <dt>Mode</dt>
                <dd>{session.mode || "greenfield"}</dd>
              </div>
              <div>
                <dt>Goal</dt>
                <dd>{session.goal || "—"}</dd>
              </div>
              <div>
                <dt>Build dir</dt>
                <dd className="mono">{buildDir || "—"}</dd>
              </div>
            </dl>
            {pkg && <InfoPanel pkg={pkg} />}
            <div className="hero-actions" style={{ marginTop: "1rem" }}>
              <button type="button" className="primary" onClick={() => onSetStage(STAGES.design)}>
                Continue to Design
              </button>
            </div>
          </section>
        )}

        {stage === STAGES.design && (
          <DesignStudioPanel
            key={session.projectId || "studio"}
            apiOk={apiOk}
            llmReady={llmReady}
            initialPhrase={session.graph.phrase || session.goal || ""}
            initialNodes={session.graph.nodes || []}
            initialEdges={session.graph.edges || []}
            initialComposeMode={session.graph.composeMode || "canvas"}
            onSessionSync={onGraphSync}
            onOpenProject={onStudioOpenProject}
          />
        )}

        {stage === STAGES.verify && (
          <div className="panel-stack">
            {!buildDir && (
              <section className="card empty-card">
                <p className="muted">
                  Compile from Design to populate KiCad verification.{" "}
                  {canReturnToDesign(session) && (
                    <button type="button" className="link-button" onClick={() => onSetStage(STAGES.design)}>
                      Return to Design
                    </button>
                  )}
                </p>
              </section>
            )}
            {buildDir && (
              <DesignPreviewPanel
                buildDir={buildDir}
                pkg={pkg}
                onGoGates={() => onSetStage(STAGES.bench)}
              />
            )}
            {displayResult?.design_quality?.copper_tier && (
              <section className="card">
                <h3>Copper honesty</h3>
                <p className="small muted">
                  DRC-clean is not fabrication-ready. Current copper tier:{" "}
                  <code>{displayResult.design_quality.copper_tier}</code>
                  {displayResult.design_quality.fab_recommendation
                    ? ` · ${displayResult.design_quality.fab_recommendation}`
                    : ""}
                </p>
              </section>
            )}
          </div>
        )}

        {stage === STAGES.bench && (
          <div className="panel-stack">
            {!buildDir && (
              <section className="card empty-card">
                <p className="muted">Bench gates need a compiled build directory.</p>
              </section>
            )}
            {pkg && <GatesPanel pkg={pkg} benchSession={session.benchSession} />}
            {buildDir && (
              <BenchPanel
                buildDir={buildDir}
                benchSession={session.benchSession}
                onRefresh={onRefreshBench}
                onSubmit={onBenchSubmit}
                onSubmitCapture={onBenchCaptureSubmit}
                onSuccess={onToast}
              />
            )}
          </div>
        )}

        {stage === STAGES.package && (
          <div className="panel-stack">
            {!pkg && (
              <section className="card empty-card">
                <p className="muted">
                  Package appears after agent-loop finalize (set a project goal in Design) or a splice
                  build.
                </p>
              </section>
            )}
            {pkg && (
              <>
                <BomPanel pkg={pkg} />
                <WiringPanel pkg={pkg} />
                <InstructionsPanel pkg={pkg} />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
