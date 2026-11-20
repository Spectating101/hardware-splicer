import { lazy, Suspense, useCallback, useEffect, useMemo, useReducer, useState } from "react";
import {
  benchStatus,
  benchSubmit,
  benchSubmitCapture,
  fetchDonorFixtures,
  fetchExamples,
  fetchHealth,
  fetchJobResult,
  fetchSceneManifest,
  fetchScenes,
  fetchJobs,
  fetchVisionCapabilities,
  renderProjectPackage,
} from "./api.js";
import BuildOverlay from "./components/BuildOverlay.jsx";
import DesignPreviewPanel from "./components/DesignPreviewPanel.jsx";
import ProductShowcase from "./components/ProductShowcase.jsx";
import DetailedAssemblyReference from "./components/DetailedAssemblyReference.jsx";
import SortingWorkcell from "./components/SortingWorkcell.jsx";
import InterfaceLabPanel from "./components/InterfaceLabPanel.jsx";
import NewProject from "./projectSession/NewProject.jsx";
import { useSpliceJob } from "./hooks/useSpliceJob.js";
import { ADVANCED_VIEWS, VIEWS, isAdvancedView } from "./nav.js";
import ProjectWorkspace from "./projectSession/ProjectWorkspace.jsx";
import { createDigitalProject } from "./projectSession/digitalStudyApi.js";
import { useProjectPersistence } from "./projectSession/projectPersistence.js";
import {
  ACTIONS,
  STAGES,
  createEmptySession,
  projectSessionReducer,
  sessionHasBuild,
  sessionIsResumable,
} from "./projectSession/projectSession.js";

const FieldDeckScene = lazy(() => import("./components/FieldDeckScene.jsx"));

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

function persistenceStatusClass(status) {
  if (status === "saving") return "job-run";
  if (status === "failed" || status === "conflict") return "job-fail";
  return "";
}

function formatProjectName(name) {
  if (!name) return "Untitled project";
  return name.replace(/_/g, " ").replace(/\s+/g, " ").trim() || "Untitled project";
}

function formatJobStatus(status) {
  if (!status) return "Unknown";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatSavedAt(value) {
  if (!value) return "Not saved";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not saved";
  return `Saved ${date.toLocaleString()}`;
}

function ProjectsHome({ projects, listError, loading, online, onStart, onLibrary, onOpen, onRetry }) {
  const [query, setQuery] = useState("");
  const matches = projects.filter((project) => formatProjectName(project.name).toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="projects-home">
    <header className="projects-heading">
      <div><h1>Projects</h1><p className="muted">Start with a build idea, adapt a reference design, or pick up where you left off.</p></div>
      <div className="hero-actions">
        <button type="button" className="secondary" onClick={onLibrary}>Browse design library</button>
        <button type="button" className="primary" data-testid="home-start-project" disabled={!online} onClick={onStart}>New project</button>
      </div>
    </header>
    <section className="card projects-collection" aria-label="Saved projects">
      <div className="projects-heading"><h2>Saved projects</h2>
        {projects.length > 0 && <label>Find a project
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>}
      </div>
      {!online && <p role="status">{loading ? "Connecting to the engineering backend…" : "The engineering backend is offline."}</p>}
      {listError && <p role="alert">{listError} <button type="button" onClick={onRetry}>Retry project list</button></p>}
      {matches.length > 0 ? <div className="project-rows">
        {matches.map((project) => <button type="button" key={project.project_id} data-project-id={project.project_id} onClick={() => onOpen(project.project_id)} disabled={!online}>
          <span><strong>{formatProjectName(project.name)}</strong><small>{formatSavedAt(project.saved_at)}</small></span>
          {project.current_stage && <span className="project-stage">{project.current_stage}</span>}
          {project.latest_revision != null && <span>Rev {project.latest_revision}</span>}
        </button>)}
      </div> : online && !listError && <p className="muted">{loading ? "Loading saved projects…" : projects.length
        ? "No projects match this name." : "Your first saved project will appear here."}</p>}
    </section>
  </div>;
}

// Every scene manifest the backend lists, opened full screen. Not part of the project journey.
function SceneManifests({ onOpenScene }) {
  const [scenes, setScenes] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetchScenes(controller.signal).then((rows) => { if (!controller.signal.aborted) setScenes(rows); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, []);
  async function open(projectId) {
    try { onOpenScene({ projectId, manifest: await fetchSceneManifest(projectId) }); }
    catch (cause) { setError(cause.message); }
  }
  return <section className="card" data-testid="advanced-scenes"><h2>Scene manifests</h2>
    {error && <p role="status">Scenes: unknown. {error}</p>}
    {scenes && !scenes.length && <p className="muted">No scene manifests found.</p>}
    {scenes?.length > 0 && <ul className="scene-manifest-list">{scenes.map((row) => <li key={row.project_id}>
      {row.geometry_status === "available"
        ? <button type="button" className="secondary" onClick={() => open(row.project_id)}>{row.title}</button>
        : <span>{row.title}</span>}
      <small className="muted"> · {row.project_id} · geometry {row.geometry_status} · {row.revisions.length} revision{row.revisions.length === 1 ? "" : "s"}</small>
    </li>)}</ul>}
  </section>;
}

function AdvancedHub({ onExamples, onLab, onOpenScene }) {
  return (
    <section className="card advanced-hub" data-testid="advanced-hub">
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
      {onOpenScene && <SceneManifests onOpenScene={onOpenScene} />}
    </section>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [examples, setExamples] = useState([]);
  const [donorFixtures, setDonorFixtures] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [visionCapabilities, setVisionCapabilities] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [view, setView] = useState(VIEWS.home);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [toast, setToast] = useState("");
  const [previewContext, setPreviewContext] = useState(null);
  const [session, dispatch] = useReducer(projectSessionReducer, undefined, () => createEmptySession());
  const [creatingDigital, setCreatingDigital] = useState(false);
  const [newEntry, setNewEntry] = useState("goal");
  const [fullScene, setFullScene] = useState(null);
  const openScene = (scene, returnTo) => { setFullScene({ ...scene, returnTo }); setView(VIEWS.fielddeck); };

  const spliceJob = useSpliceJob();
  const projectPersistence = useProjectPersistence({
    session,
    dispatch,
    enabled: Boolean(health?.ok),
  });

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

  const canResume = sessionIsResumable(session) || projectPersistence.projects.length > 0;

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
    setNewEntry("goal");
    setView(VIEWS.newProject);
  };

  const openSavedProject = useCallback(
    async (projectId) => {
      try {
        const envelope = await projectPersistence.openProject(projectId);
        setPreviewContext(null);
        setView(VIEWS.workspace);
        setToast(
          envelope?.recovery?.used
            ? `Recovered project revision ${envelope.revision}`
            : `Opened ${envelope?.snapshot?.projectName || projectId}`,
        );
      } catch (error) {
        setToast(error.message);
      }
    },
    [projectPersistence],
  );

  const resumeProject = () => {
    if (sessionIsResumable(session)) {
      setView(VIEWS.workspace);
      return;
    }
    const latest = projectPersistence.projects[0];
    if (latest) openSavedProject(latest.project_id);
  };

  const startDigitalProject = async (caseId) => {
    if (creatingDigital) return;
    setCreatingDigital(true);
    try {
      const result = await createDigitalProject(caseId);
      const envelope = result.project;
      dispatch({ type: ACTIONS.RESTORE_PROJECT_SNAPSHOT, snapshot: envelope.snapshot,
        projectId: envelope.project_id, revision: envelope.revision, savedAt: envelope.saved_at });
      setPreviewContext(null);
      setView(VIEWS.workspace);
      projectPersistence.refreshProjects();
    } finally { setCreatingDigital(false); }
  };

  const cancelIntake = () => setView(VIEWS.home);

  const completeIntake = (payload) => {
    if ([VIEWS.newProject, VIEWS.library].includes(view)) dispatch({ type: ACTIONS.RESET });
    dispatch({ type: ACTIONS.COMMIT_INTAKE, intake: payload.intake, goal: payload.goal,
      projectName: payload.projectName, composeMode: payload.composeMode, constraints: payload.constraints });
    setView(VIEWS.workspace);
  };

  const openLibrary = () => { setNewEntry("reference"); setView(VIEWS.library); };

  const startBuild = async (payload, { exampleId, route = "splice" } = {}) => {
    spliceJob.clearError();
    setPreviewContext(null);
    if ([VIEWS.newProject, VIEWS.library].includes(view)) dispatch({ type: ACTIONS.RESET });
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
    const ex =
      examples.find((r) => r.id.includes("physical_pan_tilt")) ||
      examples.find((r) => r.id.includes("money_pan_tilt")) ||
      examples.find((r) => r.id.includes("vibe_enabot_lite")) ||
      examples.find((r) => r.id.includes("robot_drive_brief")) ||
      examples[0];
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
    <div className={`app-shell${view === VIEWS.fielddeck ? " fielddeck-shell" : ""}`} data-testid="app-shell">
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
            <strong>Hardware Splicer</strong>
            <span>{health?.version ? `v${health.version}` : "Hardware-Splicer"}</span>
          </div>
          <button type="button" className="mobile-nav-toggle" aria-controls="workbench-navigation"
            aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>Menu</button>
        </div>

        <div id="workbench-navigation" className={menuOpen ? "sidebar-body open" : "sidebar-body"}
          onClick={(event) => { if (event.target.closest(".nav-button, .project-button")) setMenuOpen(false); }}>
        <nav className="sidebar-nav" aria-label="Main">
          <button
            type="button"
            className={`nav-button ${view === VIEWS.home ? "active" : ""}`}
            onClick={() => setView(VIEWS.home)}
          >
            Projects
          </button>
          {canResume && <button type="button" className={`nav-button ${inWorkspace ? "active" : ""}`}
            data-testid="nav-project" onClick={resumeProject} disabled={!health?.ok}>Resume project</button>}
          <button type="button" className={`nav-button ${[VIEWS.library, VIEWS.sortcell, VIEWS.reference, VIEWS.showcase].includes(view) ? "active" : ""}`}
            data-testid="nav-library" onClick={openLibrary}>Design library</button>
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
          {/* Reachability only: a connected engine says nothing about any project's readiness, so it stays neutral. */}
          <span
            className={`status-pill ${health?.ok || (!health && !loadError) ? "neutral" : "warn"}`}
            data-testid="engine-status"
          >
            {health?.ok ? "Connected" : !health && !loadError ? "Checking…" : "Not reachable"}
          </span>
          {loadError && (
            <button type="button" className="link-button small" onClick={loadBootstrap}>
              Retry connection
            </button>
          )}
        </div>

        {session.projectId && (
          <div className="sidebar-section">
            <div className="sidebar-label">Project state</div>
            <div className={`project-button ${persistenceStatusClass(session.persistenceStatus)}`}>
              <strong>{formatProjectName(session.projectName)}</strong>
              <span className="job-status">
                {session.persistenceStatus === "saving"
                  ? "Saving…"
                  : session.persistenceStatus === "conflict"
                    ? "Save conflict"
                    : session.persistenceStatus === "failed"
                      ? "Save failed"
                      : session.persistenceStatus === "restored" && session.snapshotRevision
                        ? `Restored r${session.snapshotRevision}`
                        : session.snapshotRevision
                          ? `Saved r${session.snapshotRevision}`
                          : "Not saved"}
              </span>
            </div>
            {session.persistenceError && <span className="muted small">{session.persistenceError}</span>}
          </div>
        )}

        {view !== VIEWS.home && projectPersistence.projects.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-label">Saved projects</div>
            <div className="project-list">
              {projectPersistence.projects.slice(0, 8).map((project) => (
                <button
                  key={project.project_id}
                  type="button"
                  className={`project-button ${session.projectId === project.project_id ? "active" : ""}`}
                  onClick={() => openSavedProject(project.project_id)}
                  title={formatSavedAt(project.saved_at)}
                >
                  <strong>{formatProjectName(project.name)}</strong>
                  <span className="job-status">
                    {[project.current_stage, project.latest_revision != null ? `r${project.latest_revision}` : null].filter(Boolean).join(" · ")}
                  </span>
                </button>
              ))}
            </div>
            {projectPersistence.listError && (
              <button type="button" className="link-button small" onClick={projectPersistence.refreshProjects}>
                Retry projects
              </button>
            )}
          </div>
        )}

        {uniqueRecentJobs.length > 0 && (
          <div className="sidebar-section sidebar-grow">
            <div className="sidebar-label">Recent builds</div>
            <div className="project-list">
              {uniqueRecentJobs.slice(0, 8).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${session.activeJobId === job.job_id ? "active" : ""} ${jobStatusClass(job.status)}`}
                  onClick={() => job.status === "succeeded" && (job.options?.job_type === "digital_study"
                    ? openSavedProject(job.options.payload.project_id) : loadJobResult(job.job_id))}
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
        </div>
      </aside>

      <main className="main">
        <div className={`content ${inWorkspace || view === VIEWS.preview || view === VIEWS.showcase || view === VIEWS.reference ? "content-results" : ""}`}>
          {view === VIEWS.home && <ProjectsHome projects={projectPersistence.projects} listError={projectPersistence.listError}
            loading={(!health && !loadError) || projectPersistence.listLoading} online={health?.ok}
            onStart={startProject} onOpen={openSavedProject} onRetry={projectPersistence.refreshProjects}
            onLibrary={openLibrary} />}

          {[VIEWS.newProject, VIEWS.library].includes(view) && <div className="library-page">
            <NewProject key={view} initialEntry={newEntry} online={health?.ok} busy={creatingDigital}
              onStartStudy={startDigitalProject} onComplete={completeIntake} onCancel={cancelIntake}
              donorFixtures={donorFixtures} visionCapabilities={visionCapabilities} llmPolicy={health?.llm_policy}
              onBuild={startBuild} building={spliceJob.active} buildError={spliceJob.error} stageLabel={spliceJob.stageLabel} />
            <section className="card"><h2>Explore reference projects</h2><div className="hero-actions">
              <button className="secondary" data-testid="nav-sortcell" onClick={() => setView(VIEWS.sortcell)}>Sorting workcell</button>
              <button className="secondary" data-testid="nav-complete-assembly" onClick={() => setView(VIEWS.reference)}>Complete CAD assembly</button>
              <button className="secondary" data-testid="nav-product-explorer" onClick={() => setView(VIEWS.showcase)}>Product explorer</button>
              <button className="secondary" onClick={() => setView(VIEWS.example)}>Example projects</button>
              <button className="secondary" onClick={handleQuickDemo} disabled={!health?.ok}>Quick demo</button>
            </div></section>
          </div>}

          {view === VIEWS.showcase && <ProductShowcase />}
          {view === VIEWS.reference && <DetailedAssemblyReference />}
          {view === VIEWS.sortcell && <SortingWorkcell />}
          {view === VIEWS.fielddeck && fullScene && (
            <Suspense fallback={null}><FieldDeckScene projectId={fullScene.projectId} manifest={fullScene.manifest}
              onExit={() => setView(fullScene.returnTo)} /></Suspense>
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
              onIntakeComplete={completeIntake}
              onReference={(target) => setView(VIEWS[target])}
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
              onProjectReload={openSavedProject}
              onOpenScene={(scene) => openScene(scene, VIEWS.workspace)}
            />
          )}

          {view === VIEWS.advanced && (
            <AdvancedHub
              onExamples={() => setView(VIEWS.example)}
              onLab={() => setView(VIEWS.lab)}
              onOpenScene={(scene) => openScene(scene, VIEWS.advanced)}
            />
          )}

          {view === VIEWS.example && (
            <div className="example-shell">
              <section className="card">
                <div className="preview-toolbar" style={{ marginBottom: "0.75rem" }}>
                  <button type="button" className="ghost" onClick={() => setView(VIEWS.advanced)}>
                    Advanced
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
                  Back to Interface Lab
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
                  Advanced
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
