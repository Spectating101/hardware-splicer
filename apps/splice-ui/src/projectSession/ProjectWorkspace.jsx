import DesignPreviewPanel from "../components/DesignPreviewPanel.jsx";
import DesignStudioPanel from "../components/DesignStudioPanel.jsx";
import ProjectWizard from "../components/ProjectWizard.jsx";
import ProjectStatusHeader from "../components/ProjectStatusHeader.jsx";
import ProjectSummaryBar from "../components/ProjectSummaryBar.jsx";
import ReadinessHero from "../components/ReadinessHero.jsx";
import TabNav from "../components/TabNav.jsx";
import {
  BomPanel,
  BenchPanel,
  GatesPanel,
  InstructionsPanel,
  WiringPanel,
} from "../components/ProjectPanels.jsx";
import { jobBundleUrl } from "../api.js";
import {
  STAGES,
  canReturnToDesign,
  sessionHasPackage,
} from "./projectSession.js";
import {
  buildStageTabs,
  copperHonestyLabel,
  evidenceLabel,
  nextStageAction,
  stageBlockReason,
  stageIsAvailable,
} from "./stageAvailability.js";

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
  const displayResult = session.displayResult;
  const stage = session.currentStage || STAGES.intake;
  const hasPkg = sessionHasPackage(session);
  const stageTabs = buildStageTabs(session);
  const next = nextStageAction(session);
  const copper = copperHonestyLabel(
    displayResult?.design_quality?.copper_tier ||
      session.designQuality?.copper_tier ||
      pkg?.gates?.copper_tier,
  );
  const evidence = evidenceLabel(session.benchSession, pkg);

  const openGateCount =
    session.benchSession?.open_gate_count ?? (session.benchSession?.open_gates || []).length;

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

  const bundleUrl = activeJobId ? jobBundleUrl(activeJobId) : null;

  return (
    <div className="project-workspace" data-testid="project-workspace">
      <ProjectStatusHeader
        session={session}
        activeJobId={activeJobId}
        bundleUrl={bundleUrl}
        onShare={() => {
          if (!bundleUrl) return;
          navigator.clipboard?.writeText(bundleUrl);
          onToast?.("Share link copied — download bundle for reviewers");
        }}
      />

      <TabNav tabs={stageTabs} activeId={stage} onChange={handleStageChange} badges={badges} />

      {next && stage !== STAGES.intake && (
        <div className="stage-next-bar" data-testid="stage-next-bar">
          <p className="muted small">Next</p>
          {next.isDownload ? (
            activeJobId && bundleUrl ? (
              <a className="primary button-link" href={bundleUrl} download data-testid="stage-next-action">
                {next.label}
              </a>
            ) : (
              <span className="muted small" data-testid="stage-next-action-disabled">
                Bundle download appears after an async job finishes
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
        <>
          <ReadinessHero
            pkg={pkg}
            benchSession={session.benchSession}
            onGoDesign={() => handleStageChange(STAGES.verify)}
            onGoBench={() => handleStageChange(STAGES.bench)}
            onGoGates={() => handleStageChange(STAGES.bench)}
          />
          <ProjectSummaryBar
            pkg={pkg}
            benchSession={session.benchSession}
            onGoBench={() => handleStageChange(STAGES.bench)}
            onGoDesign={() => handleStageChange(STAGES.verify)}
          />
        </>
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
              building={intakeBuilding}
              buildError={intakeBuildError}
              stageLabel={intakeStageLabel}
            />
          </div>
        )}

        {stage === STAGES.design && (
          <div data-testid="stage-design">
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
          </div>
        )}

        {stage === STAGES.verify && (
          <div className="panel-stack" data-testid="stage-verify">
            {!buildDir && (
              <section className="card empty-card">
                <p className="muted">
                  Compile from Design or finish Intake to populate KiCad verification.{" "}
                  {canReturnToDesign(session) && (
                    <button type="button" className="link-button" onClick={() => handleStageChange(STAGES.design)}>
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
                onGoGates={() => handleStageChange(STAGES.bench)}
              />
            )}
            {copper && (
              <section className={`card honesty-card honesty-card--${copper.tone}`} data-testid="copper-honesty">
                <h3>{copper.title}</h3>
                <p className="small muted">{copper.detail}</p>
                <p className="small muted">
                  DRC clean does <strong>not</strong> mean fabrication-ready.
                  {displayResult?.design_quality?.fab_recommendation
                    ? ` Recommendation: ${displayResult.design_quality.fab_recommendation}`
                    : ""}
                </p>
              </section>
            )}
          </div>
        )}

        {stage === STAGES.bench && (
          <div className="panel-stack" data-testid="stage-bench">
            {evidence && (
              <section className={`card honesty-card honesty-card--${evidence.tone}`} data-testid="bench-evidence-banner">
                <h3>{evidence.label}</h3>
                <p className="small muted">{evidence.detail}</p>
              </section>
            )}
            {!evidence && session.benchSession && (
              <section className="card honesty-card honesty-card--neutral" data-testid="bench-evidence-banner">
                <h3>Bench evidence</h3>
                <p className="small muted">
                  Confirm whether measurements are simulated or from a physical instrument before treating power-on as
                  field proof.
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
                  Package appears after you finish Intake build or compile from Design with a project goal set.
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
