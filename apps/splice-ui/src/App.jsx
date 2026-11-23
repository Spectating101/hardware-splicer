import { lazy, Suspense, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
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
} from "./api";
import BuildOverlay from "./components/BuildOverlay.jsx";
import DesignPreviewPanel from "./components/DesignPreviewPanel.jsx";
import ProductShowcase from "./components/ProductShowcase.jsx";
import DetailedAssemblyReference from "./components/DetailedAssemblyReference.jsx";
import SortingWorkcell from "./components/SortingWorkcell.jsx";
import InterfaceLabPanel from "./components/InterfaceLabPanel.jsx";
import NewProject from "./projectSession/NewProject.jsx";
import { useSpliceJob } from "./hooks/useSpliceJob.js";
import { ADVANCED_VIEWS, VIEWS, isAdvancedView } from "./nav.js";
import { canGoBackInApp, useRoute } from "./router";
import ProjectWorkspace from "./projectSession/ProjectWorkspace.jsx";
import { createDigitalProject } from "./projectSession/digitalStudyApi";
import { useProjectPersistence } from "./projectSession/projectPersistence";
import {
  ACTIONS,
  STAGES,
  createEmptySession,
  projectSessionReducer,
  sessionHasBuild,
  sessionIsResumable,
} from "./projectSession/projectSession.js";

const FieldDeckScene = lazy(() => import("./components/FieldDeckScene.jsx"));
const DeviceWorkspace = lazy(() => import("./device/DeviceWorkspace.jsx"));

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

// A job finishing says nothing about whether its design passed, so a completed run is neutral.
function jobStatusClass(status) {
  if (status === "succeeded") return "job-done";
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
  const text = name.replace(/_/g, " ").replace(/\s+/g, " ").trim();
  // Sentence case, so the same name saved two ways reads the same.
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Untitled project";
}

function formatDate(value) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null;
}

const SIDEBAR_RECENT = 5;

const JOB_STATUS_LABELS = { queued: "Queued", running: "Running", succeeded: "Run completed", failed: "Run failed", cancelled: "Run cancelled" };

function formatJobStatus(status, outcome) {
  if (!status) return "Unknown";
  const label = JOB_STATUS_LABELS[status] || status.charAt(0).toUpperCase() + status.slice(1);
  return outcome ? `${label} · ${outcome}` : label;
}

// What a completed study run's result says, in the backend's own terms; nothing when it says nothing.
export function jobOutcome(result) {
  if (result?.requirements_met === false) return "requirements not met";
  if (result?.requirements_met === true) return "modeled requirements met";
  return "";
}

function formatSavedAt(value) {
  if (!value) return "Not saved";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not saved";
  return `Saved ${date.toLocaleString()}`;
}

const savedTime = (project) => {
  const time = Date.parse(project.saved_at || project.created_at || "");
  return Number.isNaN(time) ? -Infinity : time;
};

// Newer first; unknown save times sort last and keep their list order.
const newerFirst = (a, b) => (b > a) - (b < a);

// Same-name projects, ordered by their newest member; each group's newest first.
export function groupProjectsByName(projects) {
  const groups = new Map();
  for (const project of projects) {
    const name = formatProjectName(project.name);
    const key = name.toLowerCase();
    if (!groups.has(key)) groups.set(key, { key, name, members: [] });
    groups.get(key).members.push(project);
  }
  return [...groups.values()].map(({ key, name, members }) => {
    const ordered = members.slice().sort((a, b) => newerFirst(savedTime(a), savedTime(b)));
    return { key, name, latest: ordered[0], older: ordered.slice(1), newest: savedTime(ordered[0]) };
  }).sort((a, b) => newerFirst(a.newest, b.newest));
}

export function ProjectsHome({ projects, listError, loading, online, onStart, onLibrary, onOpen, onRetry }) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const matches = projects.filter((project) => `${formatProjectName(project.name)} ${project.objective || ""}`.toLowerCase().includes(needle));
  // Names repeat (the same idea started twice). Projects sharing a name group under the most recently
  // saved one; the older copies fold beneath it, and the id tail tells them apart without guessing.
  const groups = groupProjectsByName(matches);
  const row = (project, repeated) => {
    const name = formatProjectName(project.name);
    const objective = project.objective && project.objective.toLowerCase() !== name.toLowerCase() ? project.objective : "";
    const created = formatDate(project.created_at);
    return <button type="button" key={project.project_id} data-project-id={project.project_id} onClick={() => onOpen(project.project_id)} disabled={!online}>
      <span className="project-row-main"><strong>{name}{repeated && <code className="project-id"> · {project.project_id.slice(0, 8)}</code>}</strong>
        {objective ? <span className="project-objective">{objective}</span>
          : !project.objective && <span className="project-objective muted">Objective · not recorded</span>}
        <small>{formatSavedAt(project.saved_at)}{created ? ` · created ${created}` : ""}</small></span>
      {project.current_stage && <span className="project-stage">{project.current_stage}</span>}
      {project.latest_revision != null && <span className="project-rev">Rev {project.latest_revision}</span>}
    </button>;
  };
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
        {groups.map(({ key, name, latest, older }) => older.length === 0 ? row(latest, false)
          : <div className="project-group" key={key} data-testid="project-group">
            {row(latest, true)}
            <details>
              <summary>{older.length} more named “{name}”</summary>
              {older.map((project) => row(project, true))}
            </details>
          </div>)}
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
  return <section className="advanced-scenes" data-testid="advanced-scenes"><h2>Scene manifests</h2>
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
          <span>Recorded manifest intakes · built through the same engine path as production; each build is checked again.</span>
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

function RouteMessage({ title, children, onHome }) {
  return <section className="card route-message" data-testid="route-message">
    <h1>{title}</h1>
    {children}
    <div className="hero-actions"><button type="button" className="secondary" onClick={onHome}>Back to projects</button></div>
  </section>;
}

function ProjectRouteState({ route, load, online, connecting, onHome, onRetry }) {
  const rev = Number.isInteger(route.revision) ? ` at revision ${route.revision}` : "";
  if (load.state === "missing") {
    return <RouteMessage title="Project not found" onHome={onHome}>
      {Number.isNaN(route.revision)
        ? <p>The link asks for a revision that is not a number. Open the project without <code>?rev=</code> to see its latest saved revision.</p>
        : <p>No saved project has the id <code>{route.projectId}</code>{rev}. It may have been deleted, or it was never saved.</p>}
    </RouteMessage>;
  }
  if (load.state === "error") {
    return <RouteMessage title="Project could not be opened" onHome={onHome}>
      <p role="alert">{load.message || "The engineering backend did not return this project."}</p>
      <button type="button" className="secondary" onClick={onRetry}>Try again</button>
    </RouteMessage>;
  }
  if (!online && !connecting) {
    return <RouteMessage title="Engineering backend not reachable" onHome={onHome}>
      <p role="status">Project <code>{route.projectId}</code> opens once the backend is reachable. Its state is unknown until then.</p>
    </RouteMessage>;
  }
  return <section className="card" aria-busy="true"><p role="status">Opening project <code>{route.projectId}</code>{rev}…</p></section>;
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [examples, setExamples] = useState([]);
  const [donorFixtures, setDonorFixtures] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [jobOutcomes, setJobOutcomes] = useState({});
  const [visionCapabilities, setVisionCapabilities] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return window.localStorage.getItem("hs.sidebarCollapsed") === "1"; } catch { return false; }
  });
  const toggleSidebar = () => setSidebarCollapsed((value) => {
    try { window.localStorage.setItem("hs.sidebarCollapsed", value ? "0" : "1"); } catch { /* per-viewer preference only */ }
    return !value;
  });
  const [route, navigate] = useRoute();
  const view = route.view;
  // In-app moves to the workspace carry no id: the URL follows the session's project id once it exists.
  const setView = useCallback((next) => navigate(next === VIEWS.workspace ? { view: next, projectId: null } : { view: next }),
    [navigate]);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [toast, setToast] = useState("");
  const [previewContext, setPreviewContext] = useState(null);
  const [session, dispatch] = useReducer(projectSessionReducer, undefined, () => createEmptySession());
  const [creatingDigital, setCreatingDigital] = useState(false);
  const [newEntry, setNewEntry] = useState("goal");
  const [fullScene, setFullScene] = useState(null);
  const [sceneError, setSceneError] = useState(null);
  const [routeLoad, setRouteLoad] = useState({ key: null, state: "idle" });
  const [routeAttempt, setRouteAttempt] = useState(0);
  const loadedRouteKey = useRef(null);
  const sessionRef = useRef(session);
  sessionRef.current = session;
  const openScene = (scene) => {
    setFullScene(scene);
    setSceneError(null);
    navigate({ view: VIEWS.fielddeck, sceneId: scene.projectId });
  };
  const exitScene = () => {
    if (canGoBackInApp()) window.history.back();
    else navigate({ view: VIEWS.home });
  };

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

  // Completed study runs carry a result summary; read it once the page is idle so it never
  // competes with the open project's own requests.
  useEffect(() => {
    const wanted = uniqueRecentJobs.slice(0, SIDEBAR_RECENT).filter((job) => job.status === "succeeded"
      && job.options?.job_type === "digital_study" && !(job.job_id in jobOutcomes));
    if (!wanted.length) return undefined;
    let cancelled = false;
    const run = () => Promise.all(wanted.map((job) => fetchJobResult(job.job_id)
      .then((body) => [job.job_id, jobOutcome(body?.result)]).catch(() => [job.job_id, ""])))
      .then((rows) => { if (!cancelled) setJobOutcomes((old) => ({ ...old, ...Object.fromEntries(rows) })); });
    const idle = window.requestIdleCallback ? window.requestIdleCallback(run, { timeout: 4000 }) : window.setTimeout(run, 2000);
    return () => {
      cancelled = true;
      if (window.cancelIdleCallback && window.requestIdleCallback) window.cancelIdleCallback(idle); else window.clearTimeout(idle);
    };
  }, [uniqueRecentJobs, jobOutcomes]);

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
        ? "Compose job finished · results not yet checked: review Verify, then Bench and Package"
        : "Build job finished · results not yet checked: review Verify, then close bench gates",
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

  const openSavedProject = useCallback((projectId) => {
    setPreviewContext(null);
    navigate({ view: VIEWS.workspace, projectId });
  }, [navigate]);

  // Re-read the saved project in place (after a run saves a revision); the URL stays put.
  const reloadProject = useCallback(async (projectId) => {
    try {
      await projectPersistence.openProject(projectId);
    } catch (error) {
      setToast(error.message);
    }
  }, [projectPersistence]);

  const openProjectRoute = projectPersistence.openProject;
  const routeKey = view === VIEWS.workspace && route.projectId
    ? `${route.projectId}@${route.revision ?? ""}#${routeAttempt}` : null;

  // A /projects/<id> URL opens that saved project (and revision) unless the session already holds it.
  useEffect(() => {
    if (!routeKey || loadedRouteKey.current === routeKey || !health?.ok) return undefined;
    const { projectId, revision } = route;
    loadedRouteKey.current = routeKey;
    if (Number.isNaN(revision)) {
      setRouteLoad({ key: routeKey, state: "missing" });
      return undefined;
    }
    const current = sessionRef.current;
    if (current.projectId === projectId
      && (revision == null || current.mode === "digital" || current.snapshotRevision === revision)) {
      setRouteLoad({ key: routeKey, state: "ready" });
      return undefined;
    }
    let cancelled = false;
    setRouteLoad({ key: routeKey, state: "loading" });
    (async () => {
      try {
        // Load the asked revision directly: loading the latest first would let it autosave in between.
        let envelope;
        try {
          envelope = await openProjectRoute(projectId, { revision });
        } catch (error) {
          if (revision == null || error.status !== 404) throw error;
          // Digital studies number their revisions on the bench, which reports an unknown one itself.
          envelope = await openProjectRoute(projectId);
          if (envelope?.snapshot?.mode !== "digital") throw error;
        }
        if (cancelled) return;
        setRouteLoad({ key: routeKey, state: "ready" });
        if (envelope?.recovery?.used) setToast(`Recovered project revision ${envelope.revision}`);
      } catch (error) {
        if (cancelled) return;
        setRouteLoad({ key: routeKey, state: error.status === 404 ? "missing" : "error", message: error.message });
      }
    })();
    return () => {
      cancelled = true;
      if (loadedRouteKey.current === routeKey) loadedRouteKey.current = null;
    };
  }, [routeKey, route, health?.ok, openProjectRoute]);

  // After an in-app move to the workspace, give the page its project URL.
  useEffect(() => {
    if (view !== VIEWS.workspace || route.projectId || !session.projectId) return;
    loadedRouteKey.current = `${session.projectId}@#${routeAttempt}`;
    setRouteLoad({ key: loadedRouteKey.current, state: "ready" });
    navigate({ view: VIEWS.workspace, projectId: session.projectId });
  }, [view, route.projectId, session.projectId, routeAttempt, navigate]);

  // A /scenes/<id> URL fetches its manifest when the scene was not opened from inside the app.
  useEffect(() => {
    if (view !== VIEWS.fielddeck || !route.sceneId || fullScene?.projectId === route.sceneId) return undefined;
    const controller = new AbortController();
    setSceneError(null);
    fetchSceneManifest(route.sceneId, controller.signal)
      .then((manifest) => { if (!controller.signal.aborted) setFullScene({ projectId: route.sceneId, manifest }); })
      .catch((cause) => { if (!controller.signal.aborted) setSceneError(cause); });
    return () => controller.abort();
  }, [view, route.sceneId, fullScene?.projectId]);

  const revisionRoute = useCallback((revision, { replace = false } = {}) => {
    if (!route.projectId) return;
    navigate({ view: VIEWS.workspace, projectId: route.projectId, revision: revision ?? null }, { replace });
  }, [navigate, route.projectId]);

  const resumeProject = () => {
    if (sessionIsResumable(session)) {
      navigate({ view: VIEWS.workspace, projectId: session.projectId });
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
  // The bench waits for the URL's project; switching revision of the open project keeps it mounted.
  const routeBlocked = inWorkspace && Boolean(route.projectId) && (session.projectId !== route.projectId
    || (routeLoad.key === routeKey && routeLoad.state !== "ready"));
  const advancedActive = isAdvancedView(view);

  return (
    <div className={`app-shell${view === VIEWS.fielddeck || view === VIEWS.device ? " fielddeck-shell" : ""}${sidebarCollapsed ? " sidebar-collapsed" : ""}`} data-testid="app-shell">
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
          <button type="button" className="sidebar-toggle" aria-controls="workbench-navigation" aria-expanded={!sidebarCollapsed}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={toggleSidebar}>
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d={sidebarCollapsed ? "M6 3l5 5-5 5" : "M10 3L5 8l5 5"}
              fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
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
          {canResume && <button type="button" className={`nav-button ${inWorkspace && !routeBlocked ? "active" : ""}`}
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
              {projectPersistence.projects.slice(0, SIDEBAR_RECENT).map((project) => (
                <button
                  key={project.project_id}
                  type="button"
                  className={`project-button ${session.projectId === project.project_id ? "active" : ""}`}
                  onClick={() => openSavedProject(project.project_id)}
                  title={formatSavedAt(project.saved_at)}
                >
                  <strong>{formatProjectName(project.name)}</strong>
                  <span className="job-status">
                    {[project.current_stage && project.current_stage.charAt(0).toUpperCase() + project.current_stage.slice(1),
                      project.latest_revision != null ? `r${project.latest_revision}` : null].filter(Boolean).join(" · ")}
                  </span>
                </button>
              ))}
            </div>
            {projectPersistence.projects.length > SIDEBAR_RECENT && <button type="button" className="link-button small sidebar-view-all"
              data-testid="sidebar-view-all" onClick={() => navigate({ view: VIEWS.home })}>
              View all {projectPersistence.projects.length} projects</button>}
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
              {uniqueRecentJobs.slice(0, SIDEBAR_RECENT).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${session.activeJobId === job.job_id ? "active" : ""} ${jobStatusClass(job.status)}`}
                  onClick={() => job.status === "succeeded" && (job.options?.job_type === "digital_study"
                    ? openSavedProject(job.options.payload.project_id) : loadJobResult(job.job_id))}
                  disabled={job.status !== "succeeded"}
                  title={formatJobStatus(job.status, jobOutcomes[job.job_id])}
                >
                  <strong>{formatProjectName(job.project_name || job.job_id)}</strong>
                  <span className="job-status">{formatJobStatus(job.status, jobOutcomes[job.job_id])}</span>
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
              <button className="secondary" data-testid="nav-complete-assembly" onClick={() => setView(VIEWS.reference)}>Full CAD assembly reference</button>
              <button className="secondary" data-testid="nav-product-explorer" onClick={() => setView(VIEWS.showcase)}>Product explorer</button>
              <button className="secondary" onClick={() => setView(VIEWS.example)}>Example projects</button>
              <button className="secondary" onClick={handleQuickDemo} disabled={!health?.ok}>Quick demo</button>
            </div></section>
          </div>}

          {view === VIEWS.showcase && <ProductShowcase />}
          {view === VIEWS.reference && <DetailedAssemblyReference />}
          {view === VIEWS.sortcell && <SortingWorkcell />}
          {view === VIEWS.fielddeck && fullScene?.projectId === route.sceneId && (
            <Suspense fallback={null}><FieldDeckScene projectId={fullScene.projectId} manifest={fullScene.manifest}
              onExit={exitScene} exitLabel={canGoBackInApp() ? "Back to the previous page" : "Back to projects"} /></Suspense>
          )}
          {view === VIEWS.fielddeck && fullScene?.projectId !== route.sceneId && (sceneError
            ? <RouteMessage title={sceneError.status === 404 ? "Scene not found" : "Scene could not be opened"}
              onHome={() => navigate({ view: VIEWS.home })}>
              <p>{sceneError.status === 404 ? <>No scene manifest has the id <code>{route.sceneId}</code>.</> : sceneError.message}</p>
            </RouteMessage>
            : <section className="card" aria-busy="true"><p role="status">Opening scene <code>{route.sceneId}</code>…</p></section>)}

          {view === VIEWS.device && route.sceneId && (
            <Suspense fallback={null}><DeviceWorkspace sceneId={route.sceneId} onExit={exitScene} /></Suspense>
          )}

          {view === VIEWS.notFound && <RouteMessage title="Page not found" onHome={() => navigate({ view: VIEWS.home })}>
            <p>Nothing in Hardware Splicer lives at <code>{route.path}</code>.</p>
          </RouteMessage>}

          {routeBlocked && (
            <ProjectRouteState route={route} load={routeLoad.key === routeKey ? routeLoad : { state: "loading" }}
              online={health?.ok} connecting={!health && !loadError} onHome={() => navigate({ view: VIEWS.home })}
              onRetry={() => setRouteAttempt((value) => value + 1)} />
          )}

          {view === VIEWS.workspace && !routeBlocked && (
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
              onProjectReload={reloadProject}
              routeRevision={route.revision}
              readOnlyRevision={Boolean(session.projectId) && projectPersistence.historicalProjectId === session.projectId}
              onRevisionRoute={route.projectId ? revisionRoute : undefined}
              onOpenScene={openScene}
            />
          )}

          {view === VIEWS.advanced && (
            <AdvancedHub
              onExamples={() => setView(VIEWS.example)}
              onLab={() => setView(VIEWS.lab)}
              onOpenScene={openScene}
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
                <p className="muted">Recorded manifest intakes · built through the same engine path as production; each build is checked again.</p>
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
