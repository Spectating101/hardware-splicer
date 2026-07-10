import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import {
  benchStatus,
  benchSubmit,
  benchSubmitCapture,
  fetchDonorFixtures,
  fetchExamples,
  fetchHealth,
  fetchJobResult,
  fetchJobs,
  fetchVisionCapabilities,
  renderProjectPackage,
} from "./api.js";
import BuildOverlay from "./components/BuildOverlay.jsx";
import DesignPreviewPanel from "./components/DesignPreviewPanel.jsx";
import InterfaceLabPanel from "./components/InterfaceLabPanel.jsx";
import PipelineVisual from "./components/PipelineVisual.jsx";
import { StatusPill } from "./components/ProjectPanels.jsx";
import { useSpliceJob } from "./hooks/useSpliceJob.js";
import { ADVANCED_VIEWS, VIEWS, isAdvancedView } from "./nav.js";
import ProjectWorkspace from "./projectSession/ProjectWorkspace.jsx";
import {
  ACTIONS,
  STAGES,
  createEmptySession,
  projectSessionReducer,
  sessionHasBuild,
  sessionIsResumable,
} from "./projectSession/projectSession.js";

function Toast({ message, onDismiss }) {
  useEffect(() => {
    if (!message) return undefined;
    const t = setTimeout(onDismiss, 4000);
    return () => clearTimeout(t);
  }, [message, onDismiss]);
  if (!message) return null;
  return (
    <div className="toast" role="status">
      {message}
    </div>
  );
}

function jobStatusClass(status) {
  if (status === "succeeded") return "job-ok";
  if (status === "failed" || status === "cancelled") return "job-fail";
  if (status === "running" || status === "queued") return "job-run";
  return "";
}

function formatProjectName(name) {
  if (!name) return "Untitled build";
  return name.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

function formatJobStatus(status) {
  if (!status) return "Unknown";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function HomeHero({ onStart, onResume, canResume, onExample, onQuickDemo, apiOk, version }) {
  return (
    <div className="home-layout">
      <section className="home-hero card">
        <p className="eyebrow">Hardware-Splicer · Splice Agent {version ? `v${version}` : ""}</p>
        <h1>AI-assisted KiCad design — canvas to DRC truth to bench-ready package</h1>
        <p className="lead">
          <strong>Agents and humans</strong> share one spine: MCP/HTTP compose → KiCad DRC fix loop →{" "}
          <code>PROJECT_PACKAGE</code> → bench gates. Salvage splice and donor vision when bring-up matters.
        </p>
        <div className="readiness-pitch">
          <strong>Flux-class first mile. Auditable last mile.</strong>
          <p className="muted small">
            One project workspace: Intake → Design → Verify → Bench → Package. Same compile truth as{" "}
            <code>hs_compose_drc_agent</code>. Session continuity is in-memory while this page is open.
          </p>
        </div>
        <PipelineVisual />
        <div className="hero-actions">
          {canResume ? (
            <>
              <button type="button" className="primary large" onClick={onResume} disabled={!apiOk}>
                Resume project
              </button>
              <button type="button" className="secondary large" onClick={onStart} disabled={!apiOk}>
                Start new project
              </button>
            </>
          ) : (
            <button
              type="button"
              className="primary large"
              onClick={onStart}
              disabled={!apiOk}
              data-testid="home-start-project"
            >
              Start a project
            </button>
          )}
          <button type="button" className="secondary large" onClick={onQuickDemo} disabled={!apiOk}>
            Quick demo (1-click)
          </button>
          <button type="button" className="ghost large" onClick={onExample} disabled={!apiOk}>
            Browse examples
          </button>
        </div>
        {!apiOk && (
          <div className="offline-box">
            <strong>API offline</strong>
            <p>
              Run <code>hs-serve --port 8787</code> or{" "}
              <code>HARDWARE_SPLICER_SERVE_UI=1 hs-serve</code> for single-port mode.
            </p>
          </div>
        )}
      </section>
      <aside className="home-aside card">
        <h3>What you get</h3>
        <ul className="feature-list">
          <li>
            <span className="feature-icon">✦</span>
            <div>
              <strong>AI compose</strong>
              <span>LLM-first module pick → KiCad (Flux-class path)</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">◇</span>
            <div>
              <strong>Live sourcing</strong>
              <span>JLC/LCSC enrich on compile BOM</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">⚡</span>
            <div>
              <strong>KiCad carrier</strong>
              <span>Honest DRC — not cosmetic copper fiction</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">📋</span>
            <div>
              <strong>Project package</strong>
              <span>BOM, wiring, build steps in one bundle</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">◇</span>
            <div>
              <strong>Design verification</strong>
              <span>KiCanvas preview, BOM, fab artifact coverage</span>
            </div>
          </li>
          <li>
            <span className="feature-icon">🛡</span>
            <div>
              <strong>Safety gates</strong>
              <span>Bench measurements before power-on</span>
            </div>
          </li>
        </ul>
      </aside>
    </div>
  );
}

function AdvancedHub({ onExamples, onLab }) {
  return (
    <section className="card advanced-hub" data-testid="advanced-hub">
      <p className="eyebrow">Advanced</p>
      <h1>Developer tools</h1>
      <p className="muted">
        Adapters and demos that are not part of the normal project journey. Prefer{" "}
        <strong>Start a project</strong> for day-to-day work.
      </p>
      <div className="advanced-grid">
        <button type="button" className="fixture-card" onClick={onExamples} data-testid="advanced-examples">
          <strong>Examples</strong>
          <span>Proven manifest intakes — same engine path as production.</span>
        </button>
        <button type="button" className="fixture-card" onClick={onLab} data-testid="advanced-lab">
          <strong>Interface Lab</strong>
          <span>Integration adapters, netlist fixtures, and design-preview probes.</span>
        </button>
      </div>
    </section>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [examples, setExamples] = useState([]);
  const [donorFixtures, setDonorFixtures] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [visionCapabilities, setVisionCapabilities] = useState(null);
  const [view, setView] = useState(VIEWS.home);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [toast, setToast] = useState("");
  const [previewContext, setPreviewContext] = useState(null);
  const [session, dispatch] = useReducer(projectSessionReducer, undefined, () => createEmptySession());

  const spliceJob = useSpliceJob();

  const uniqueRecentJobs = useMemo(() => {
    const seen = new Set();
    return recentJobs.filter((job) => {
      const key = job.project_name || job.job_id;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [recentJobs]);

  const selectedExample = useMemo(
    () => examples.find((row) => row.id === selectedExampleId) || examples[0] || null,
    [examples, selectedExampleId],
  );

  const buildingName =
    session.projectPackage?.info?.project_name ||
    session.projectName ||
    spliceJob.job?.project_name ||
    selectedExample?.label ||
    "project";

  const canResume = sessionIsResumable(session);

  const loadBootstrap = useCallback(async () => {
    setLoadError(null);
    try {
      const healthRes = await fetchHealth();
      setHealth(healthRes);
    } catch (err) {
      setHealth(null);
      setLoadError(err.message);
      return;
    }
    try {
      const [examplesRes, fixturesRes, jobsRes, visionRes] = await Promise.all([
        fetchExamples(),
        fetchDonorFixtures(),
        fetchJobs({ limit: 12 }),
        fetchVisionCapabilities().catch(() => null),
      ]);
      setExamples(examplesRes.examples || []);
      setDonorFixtures(fixturesRes.fixtures || []);
      setRecentJobs(jobsRes.jobs || []);
      setVisionCapabilities(visionRes);
      if ((examplesRes.examples || []).length && !selectedExampleId) {
        setSelectedExampleId(examplesRes.examples[0].id);
      }
    } catch (err) {
      setLoadError(err.message);
    }
  }, [selectedExampleId]);

  useEffect(() => {
    loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (!spliceJob.result) return;
    dispatch({
      type: ACTIONS.HYDRATE_CURRENT_RESULT,
      jobId: spliceJob.job?.job_id || null,
      result: spliceJob.result,
      benchSession: spliceJob.result.bench_session || null,
      stage: STAGES.verify,
    });
    setPreviewContext(null);
    setView(VIEWS.workspace);
    loadBootstrap();
    setToast(
      spliceJob.jobKind === "compose"
        ? "AI compose complete — review Verify, then Bench and Package"
        : "Build complete — review Verify, then close bench gates",
    );
  }, [spliceJob.result, spliceJob.jobKind, spliceJob.job?.job_id, loadBootstrap]);

  useEffect(() => {
    if (!session.buildDir) return;
    benchStatus(session.buildDir)
      .then((bench) => dispatch({ type: ACTIONS.SET_BENCH_SESSION, benchSession: bench }))
      .catch(() => {});
  }, [session.buildDir]);

  const refreshBench = useCallback(async () => {
    if (!session.buildDir) return;
    const bench = await benchStatus(session.buildDir);
    dispatch({ type: ACTIONS.SET_BENCH_SESSION, benchSession: bench });
    return bench;
  }, [session.buildDir]);

  const startProject = () => {
    dispatch({ type: ACTIONS.START_PROJECT });
    setView(VIEWS.workspace);
  };

  const resumeProject = () => {
    setView(VIEWS.workspace);
  };

  const cancelIntake = () => {
    dispatch({ type: ACTIONS.RESET });
    setView(VIEWS.home);
  };

  const startBuild = async (payload, { exampleId, route = "splice" } = {}) => {
    spliceJob.clearError();
    setPreviewContext(null);
    dispatch({ type: ACTIONS.START_FROM_INTAKE, intake: payload });
    setView(VIEWS.workspace);
    const jobId =
      route === "compose"
        ? await spliceJob.startCompose(payload, { exportGerber: false })
        : await spliceJob.startBuild(payload, { exportGerber: false });
    dispatch({ type: ACTIONS.SET_ACTIVE_JOB, jobId });
    if (exampleId) setSelectedExampleId(exampleId);
  };

  const loadJobResult = async (jobId) => {
    spliceJob.reset();
    setPreviewContext(null);
    const payload = await fetchJobResult(jobId);
    if (payload.ok && payload.result) {
      const dir = payload.result.build_dir || payload.result.project_package?.build_dir;
      let bench = null;
      if (dir) {
        try {
          bench = await benchStatus(dir);
        } catch {
          bench = null;
        }
      }
      dispatch({
        type: ACTIONS.LOAD_RECENT_BUILD,
        jobId,
        result: payload.result,
        benchSession: bench,
        stage: STAGES.verify,
      });
      setView(VIEWS.workspace);
    }
  };

  const handleQuickDemo = () => {
    const ex = examples.find((r) => r.id.includes("robot_drive_brief")) || examples[0];
    if (ex?.intake) startBuild(ex.intake, { exampleId: ex.id, route: "splice" });
  };

  const openStudioProject = async ({ composeResult, drc }) => {
    const buildDir = drc?.outDir || composeResult?.out_dir;
    if (!buildDir) return;
    try {
      const [pkgRes, bench] = await Promise.all([
        renderProjectPackage(buildDir, { source: "compose" }),
        benchStatus(buildDir),
      ]);
      spliceJob.reset();
      dispatch({
        type: ACTIONS.APPLY_STUDIO_COMPILE,
        composeResult,
        drc,
        projectPackage: pkgRes.package,
        benchSession: bench,
        buildDir,
        // no jobId — clear any stale recent-job bundle link
      });
      setView(VIEWS.workspace);
      setToast("Moved to Verify — same project; Design graph kept");
    } catch (err) {
      setToast(err.message);
    }
  };

  const handleGraphSync = useCallback((patch) => {
    dispatch({ type: ACTIONS.SYNC_GRAPH, ...patch });
  }, []);

  const openDesignPreview = ({ buildDir, title, qualityHint }) => {
    if (!buildDir) return;
    setPreviewContext({ buildDir, title, qualityHint });
    setView(VIEWS.preview);
    setToast("KiCad preview opened");
  };

  const handleRunRepairCafeDemo = () => {
    const ex =
      examples.find((r) => r.id.includes("repair_cafe")) ||
      examples.find((r) => r.id.includes("robot_drive_brief")) ||
      examples[0];
    if (ex?.intake) startBuild(ex.intake, { exampleId: ex.id, route: "splice" });
  };

  const handleBenchSubmit = async (measurements) => {
    if (!session.buildDir) return;
    const bench = await benchSubmit(session.buildDir, measurements);
    dispatch({ type: ACTIONS.PATCH_PACKAGE_GATES, benchSession: bench });
    return bench;
  };

  const handleBenchCaptureSubmit = async (capture) => {
    if (!session.buildDir) return null;
    const result = await benchSubmitCapture(session.buildDir, capture);
    if (result?.bench_session) {
      dispatch({ type: ACTIONS.PATCH_PACKAGE_GATES, benchSession: result.bench_session });
    }
    return result;
  };

  const inWorkspace = view === VIEWS.workspace;
  const advancedActive = isAdvancedView(view);

  return (
    <div className="app-shell" data-testid="app-shell">
      <BuildOverlay
        active={spliceJob.active}
        status={spliceJob.job?.status}
        stageLabel={spliceJob.stageLabel}
        elapsedSec={spliceJob.elapsedSec}
        error={!spliceJob.active ? spliceJob.error : null}
        projectName={buildingName}
      />
      <Toast message={toast} onDismiss={() => setToast("")} />

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            HS
          </div>
          <div>
            <strong>Splice Agent</strong>
            <span>{health?.version ? `v${health.version}` : "Hardware-Splicer"}</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main">
          <button
            type="button"
            className={`nav-button ${view === VIEWS.home ? "active" : ""}`}
            onClick={() => setView(VIEWS.home)}
          >
            Home
          </button>
          <button
            type="button"
            className={`nav-button ${inWorkspace ? "active" : ""}`}
            data-testid="nav-project"
            onClick={() => {
              if (!session.projectId) {
                startProject();
                return;
              }
              setView(VIEWS.workspace);
            }}
            disabled={!health?.ok}
          >
            Project
          </button>
          <button
            type="button"
            className={`nav-button ${advancedActive ? "active" : ""}`}
            data-testid="nav-advanced"
            onClick={() => setView(VIEWS.advanced)}
          >
            Advanced
          </button>
        </nav>

        {advancedActive && (
          <div className="sidebar-section">
            <div className="sidebar-label">Advanced</div>
            <button
              type="button"
              className={`nav-button nested ${view === VIEWS.example ? "active" : ""}`}
              onClick={() => setView(VIEWS.example)}
            >
              Examples
            </button>
            <button
              type="button"
              className={`nav-button nested ${view === VIEWS.lab || view === VIEWS.preview ? "active" : ""}`}
              data-testid="nav-interface-lab"
              onClick={() => setView(VIEWS.lab)}
            >
              Interface Lab
            </button>
          </div>
        )}

        <div className="sidebar-section">
          <div className="sidebar-label">Engine</div>
          <StatusPill ok={health?.ok} label={health?.ok ? "Online" : "Offline"} />
          {loadError && (
            <button type="button" className="link-button small" onClick={loadBootstrap}>
              Retry connection
            </button>
          )}
        </div>

        {uniqueRecentJobs.length > 0 && (
          <div className="sidebar-section sidebar-grow">
            <div className="sidebar-label">Recent builds</div>
            <div className="project-list">
              {uniqueRecentJobs.slice(0, 8).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${session.activeJobId === job.job_id ? "active" : ""} ${jobStatusClass(job.status)}`}
                  onClick={() => job.status === "succeeded" && loadJobResult(job.job_id)}
                  disabled={job.status !== "succeeded"}
                  title={job.status}
                >
                  <strong>{formatProjectName(job.project_name || job.job_id)}</strong>
                  <span className="job-status">{formatJobStatus(job.status)}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>

      <main className="main">
        <div className={`content ${inWorkspace || view === VIEWS.preview ? "content-results" : ""}`}>
          {view === VIEWS.home && (
            <HomeHero
              apiOk={health?.ok}
              version={health?.version}
              canResume={canResume}
              onStart={startProject}
              onResume={resumeProject}
              onExample={() => setView(VIEWS.example)}
              onQuickDemo={handleQuickDemo}
            />
          )}

          {view === VIEWS.workspace && (
            <ProjectWorkspace
              session={session}
              onSetStage={(stage) => dispatch({ type: ACTIONS.SET_STAGE, stage })}
              apiOk={health?.ok}
              llmReady={Boolean(health?.llm_policy?.qwen_llm_first)}
              donorFixtures={donorFixtures}
              visionCapabilities={visionCapabilities}
              llmPolicy={health?.llm_policy}
              onIntakeBuild={(payload, options) => startBuild(payload, options)}
              onIntakeCancel={cancelIntake}
              intakeBuilding={spliceJob.active}
              intakeBuildError={spliceJob.error}
              intakeStageLabel={spliceJob.stageLabel}
              onStudioOpenProject={openStudioProject}
              onGraphSync={handleGraphSync}
              onRefreshBench={() => refreshBench()}
              onBenchSubmit={handleBenchSubmit}
              onBenchCaptureSubmit={handleBenchCaptureSubmit}
              onToast={setToast}
              activeJobId={session.activeJobId}
            />
          )}

          {view === VIEWS.advanced && (
            <AdvancedHub
              onExamples={() => setView(VIEWS.example)}
              onLab={() => setView(VIEWS.lab)}
            />
          )}

          {view === VIEWS.example && (
            <div className="example-shell">
              <section className="card">
                <div className="preview-toolbar" style={{ marginBottom: "0.75rem" }}>
                  <button type="button" className="ghost" onClick={() => setView(VIEWS.advanced)}>
                    ← Advanced
                  </button>
                </div>
                <h2>Example projects</h2>
                <p className="muted">Proven manifest intakes — same engine path as production.</p>
                <div className="example-grid">
                  {examples.map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      className={`fixture-card ${selectedExample?.id === row.id ? "active" : ""}`}
                      onClick={() => setSelectedExampleId(row.id)}
                    >
                      <strong>{row.label}</strong>
                      <span>{row.goal}</span>
                    </button>
                  ))}
                </div>
                <div className="example-actions">
                  <button
                    type="button"
                    className="primary"
                    disabled={!selectedExample || spliceJob.active || !health?.ok}
                    onClick={() =>
                      selectedExample?.intake &&
                      startBuild(selectedExample.intake, {
                        exampleId: selectedExample.id,
                        route: "splice",
                      })
                    }
                  >
                    Build selected example
                  </button>
                </div>
              </section>
            </div>
          )}

          {view === VIEWS.preview && (
            <div className="preview-shell">
              <div className="preview-toolbar card">
                <button type="button" className="ghost" onClick={() => setView(VIEWS.lab)}>
                  ← Back to Interface Lab
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setPreviewContext(null);
                    setView(sessionHasBuild(session) ? VIEWS.workspace : VIEWS.home);
                  }}
                >
                  {sessionHasBuild(session) ? "Open project workspace" : "Home"}
                </button>
              </div>
              <DesignPreviewPanel
                buildDir={previewContext?.buildDir || session.buildDir}
                qualityHint={previewContext?.qualityHint}
                title={previewContext?.title}
                onGoGates={
                  sessionHasBuild(session)
                    ? () => {
                        setPreviewContext(null);
                        dispatch({ type: ACTIONS.SET_STAGE, stage: STAGES.bench });
                        setView(VIEWS.workspace);
                      }
                    : null
                }
              />
            </div>
          )}

          {view === VIEWS.lab && (
            <div className="lab-shell" data-testid="interface-lab">
              <div className="preview-toolbar" style={{ marginBottom: "0.75rem" }}>
                <button type="button" className="ghost" onClick={() => setView(VIEWS.advanced)}>
                  ← Advanced
                </button>
              </div>
              <InterfaceLabPanel
                llmPolicy={health?.llm_policy}
                onOpenDesignPreview={openDesignPreview}
                onRunFullDemo={handleRunRepairCafeDemo}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Re-export for tests
export { ADVANCED_VIEWS, VIEWS };
