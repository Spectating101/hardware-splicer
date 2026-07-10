import DesignPreviewPanel from "../components/DesignPreviewPanel.jsx";
import DesignStudioPanel from "../components/DesignStudioPanel.jsx";
import ProjectWizard from "../components/ProjectWizard.jsx";
import ProjectStatusHeader from "../components/ProjectStatusHeader.jsx";
import ProjectReadinessPanel from "../components/ProjectReadinessPanel.jsx";
import TabNav from "../components/TabNav.jsx";
import {
  BomPanel,
  BenchPanel,
  GatesPanel,
  InstructionsPanel,
  WiringPanel,
} from "../components/ProjectPanels.jsx";
import {
  STAGES,
  sessionHasPackage,
} from "./projectSession.js";
import {
  buildStageTabs,
  nextStageAction,
  stageBlockReason,
  stageIsAvailable,
} from "./stageAvailability.js";
import { deriveProjectTruth } from "./deriveProjectTruth.js";
import { derivePackageHandoff } from "./packageHandoff.js";

/**
 * Project workspace shell — stages wrap existing panels.
 * Session continuity is in-memory only (no localStorage).
 */
export default function ProjectWorkspace({
  session,
  onSetStage,
  apiOk,
  llmReady,
  donorFixtures,
  visionCapabilities,
  llmPolicy,
  onIntakeBuild,
  onIntakeComplete,
  onIntakeCancel,
  intakeBuilding,
  intakeBuildError,
  intakeStageLabel,
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
  const stage = session.currentStage || STAGES.intake;
  const hasPkg = sessionHasPackage(session);
  const stageTabs = buildStageTabs(session);
  const next = nextStageAction(session);
  const truth = deriveProjectTruth(session);
  const handoff = derivePackageHandoff(session);

  const openGateCount = truth.bench.openGateCount;

  const badges = {
    [STAGES.bench]: openGateCount,
  };

  const handleStageChange = (nextStage) => {
    if (!stageIsAvailable(session, nextStage)) {
      onToast?.(stageBlockReason(session, nextStage) || "Stage not available yet");
      return;
    }
    onSetStage(nextStage);
  };

  return (
    <div className="project-workspace" data-testid="project-workspace">
      <ProjectStatusHeader
        session={session}
        activeJobId={activeJobId}
        onShare={(link) => {
          const url = link?.url || handoff.url;
          if (!url) return;
          navigator.clipboard?.writeText(url);
          onToast?.("Share link copied — download package for reviewers");
        }}
      />

      <TabNav tabs={stageTabs} activeId={stage} onChange={handleStageChange} badges={badges} />

      {next && stage !== STAGES.intake && (
        <div className="stage-next-bar" data-testid="stage-next-bar">
          <p className="muted small">Next</p>
          {next.isDownload ? (
            next.handoff?.available && next.handoff.url ? (
              <a
                className="primary button-link"
                href={next.handoff.url}
                download
                data-testid="stage-next-action"
              >
                {next.label}
              </a>
            ) : (
              <span className="muted small" data-testid="stage-next-action-disabled">
                {next.handoff?.explanation ||
                  "Package download is unavailable for this session"}
              </span>
            )
          ) : (
            <button
              type="button"
              className="primary"
              data-testid="stage-next-action"
              disabled={!next.enabled}
              onClick={() => next.enabled && next.stage && handleStageChange(next.stage)}
            >
              {next.label}
            </button>
          )}
        </div>
      )}

      {hasPkg && stage !== STAGES.design && stage !== STAGES.intake && (
        <ProjectReadinessPanel session={session} onGoStage={handleStageChange} />
      )}

      <div className="workspace-stage">
        {stage === STAGES.intake && (
          <div data-testid="stage-intake">
            <ProjectWizard
              key={session.projectId || "intake"}
              embedded
              donorFixtures={donorFixtures}
              visionCapabilities={visionCapabilities}
              llmPolicy={llmPolicy}
              onCancel={onIntakeCancel}
              onBuild={onIntakeBuild}
              onCompleteIntake={onIntakeComplete}
              building={intakeBuilding}
              buildError={intakeBuildError}
              stageLabel={intakeStageLabel}
            />
          </div>
        )}

        {stage === STAGES.design && (
          <div data-testid="stage-design">
            {session.designEditable === false ? (
              <section className="card empty-card" data-testid="design-not-editable">
                <h2>No editable Studio graph</h2>
                <p className="muted">
                  No editable Studio graph was stored for this build. Verify, Bench, and Package still show the compiled
                  artifacts. Start a new greenfield project to design in Studio.
                </p>
                <p className="small muted">Goal on record: {session.goal || "—"}</p>
              </section>
            ) : (
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
                showIntakeEmptyState={Boolean(session.intakeComplete && !(session.graph.nodes || []).length)}
              />
            )}
          </div>
        )}

        {stage === STAGES.verify && (
          <div className="panel-stack" data-testid="stage-verify">
            {!buildDir && (
              <section className="card empty-card">
                <p className="muted">Compile from Design or finish a salvage build to populate verification.</p>
              </section>
            )}
            {buildDir && (
              <DesignPreviewPanel
                buildDir={buildDir}
                pkg={pkg}
                onGoGates={() => handleStageChange(STAGES.bench)}
              />
            )}
            {truth.copper.state === "preview_only" && (
              <section className="card honesty-card honesty-card--warn" data-testid="copper-honesty">
                <h3>{truth.copper.label}</h3>
                <p className="small muted">{truth.copper.detail}</p>
                <p className="small muted">
                  Design clean · Copper preview only · <strong>Not fabrication-ready</strong>
                </p>
              </section>
            )}
          </div>
        )}

        {stage === STAGES.bench && (
          <div className="panel-stack" data-testid="stage-bench">
            {(truth.bench.simulated ||
              truth.bench.state === "authorization_pending" ||
              truth.bench.state === "gates_open" ||
              truth.bench.state === "physical_authorized") && (
              <section
                className={`card honesty-card honesty-card--${
                  truth.bench.simulated
                    ? "warn"
                    : truth.bench.state === "authorization_pending"
                      ? "warn"
                      : "neutral"
                }`}
                data-testid="bench-evidence-banner"
              >
                <h3>
                  {truth.bench.simulated
                    ? "Simulated evidence"
                    : truth.bench.state === "authorization_pending"
                      ? "Authorization pending"
                      : "Bench evidence"}
                </h3>
                <p className="small muted">
                  {truth.bench.simulated
                    ? "Simulated evidence is not physical café measurement."
                    : truth.bench.state === "authorization_pending"
                      ? "Measurements may be recorded, but power-on is not authorized without explicit simulated or physical provenance."
                      : "Confirm whether measurements are simulated or from a physical instrument before treating power-on as field proof."}
                </p>
              </section>
            )}
            {!buildDir && (
              <section className="card empty-card">
                <p className="muted">Bench gates need a compiled board first.</p>
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
          <div className="panel-stack" data-testid="stage-package">
            {!pkg && (
              <section className="card empty-card">
                <p className="muted">
                  Package appears after Design compile with a project goal, or after a salvage build.
                </p>
              </section>
            )}
            {pkg && (
              <>
                <section className="card" data-testid="package-handoff">
                  <h3>Project package handoff</h3>
                  {handoff.available && handoff.url ? (
                    <>
                      <p className="muted small">{handoff.explanation}</p>
                      <a
                        className="primary button-link"
                        href={handoff.url}
                        download
                        data-testid="package-download"
                      >
                        Download project package
                      </a>
                    </>
                  ) : (
                    <p className="muted small" data-testid="package-handoff-unavailable">
                      {handoff.explanation}
                    </p>
                  )}
                </section>
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
