import { useCallback, useEffect, useMemo, useState } from "react";
import {
  benchStatus,
  benchSubmit,
  fetchDonorFixtures,
  fetchExamples,
  fetchHealth,
  fetchJobResult,
  fetchJobs,
  jobBundleUrl,
} from "./api.js";
import BuildOverlay from "./components/BuildOverlay.jsx";
import DesignPreviewPanel from "./components/DesignPreviewPanel.jsx";
import InterfaceLabPanel from "./components/InterfaceLabPanel.jsx";
import PipelineVisual from "./components/PipelineVisual.jsx";
import ProjectSummaryBar from "./components/ProjectSummaryBar.jsx";
import ProjectWizard from "./components/ProjectWizard.jsx";
import TabNav from "./components/TabNav.jsx";
import {
  BomPanel,
  BenchPanel,
  GatesPanel,
  InfoPanel,
  InstructionsPanel,
  PROJECT_TABS,
  StatusPill,
  WiringPanel,
} from "./components/ProjectPanels.jsx";
import { useSpliceJob } from "./hooks/useSpliceJob.js";

const VIEWS = {
  home: "home",
  wizard: "wizard",
  example: "example",
  results: "results",
  lab: "lab",
};

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

function HomeHero({ onStart, onExample, onQuickDemo, apiOk, version }) {
  return (
    <div className="home-layout">
      <section className="home-hero card">
        <p className="eyebrow">Hardware-Splicer · Splice Agent {version ? `v${version}` : ""}</p>
        <h1>Salvage hardware you can defend on the bench</h1>
        <p className="lead">
          Turn donor parts into a KiCad carrier, parts list, wiring guide, and{" "}
          <strong>measurement gates</strong> you must close before power-on.
        </p>
        <PipelineVisual />
        <div className="hero-actions">
          <button type="button" className="primary large" onClick={onStart} disabled={!apiOk}>
            Start a project
          </button>
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

export default function App() {
  const [health, setHealth] = useState(null);
  const [examples, setExamples] = useState([]);
  const [donorFixtures, setDonorFixtures] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [view, setView] = useState(VIEWS.home);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [activeTab, setActiveTab] = useState("info");
  const [benchSession, setBenchSession] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [hydratedResult, setHydratedResult] = useState(null);
  const [toast, setToast] = useState("");

  const spliceJob = useSpliceJob();

  const selectedExample = useMemo(
    () => examples.find((row) => row.id === selectedExampleId) || examples[0] || null,
    [examples, selectedExampleId],
  );

  const displayResult = spliceJob.result || hydratedResult;
  const displayPackage = displayResult?.project_package || null;
  const displayBuildDir = displayResult?.build_dir || displayPackage?.build_dir || null;
  const buildingName =
    displayPackage?.info?.project_name ||
    spliceJob.job?.project_name ||
    selectedExample?.label ||
    "project";

  const openGateCount = benchSession?.open_gate_count ?? (benchSession?.open_gates || []).length;

  const tabBadges = useMemo(
    () => ({
      gates: openGateCount,
      bench: openGateCount,
    }),
    [openGateCount],
  );

  const loadBootstrap = useCallback(async () => {
    setLoadError(null);
    try {
      const [healthRes, examplesRes, fixturesRes, jobsRes] = await Promise.all([
        fetchHealth(),
        fetchExamples(),
        fetchDonorFixtures(),
        fetchJobs({ limit: 12 }),
      ]);
      setHealth(healthRes);
      setExamples(examplesRes.examples || []);
      setDonorFixtures(fixturesRes.fixtures || []);
      setRecentJobs(jobsRes.jobs || []);
      if ((examplesRes.examples || []).length && !selectedExampleId) {
        setSelectedExampleId(examplesRes.examples[0].id);
      }
    } catch (err) {
      setLoadError(err.message);
      setHealth(null);
    }
  }, [selectedExampleId]);

  useEffect(() => {
    loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (spliceJob.result) {
      setView(VIEWS.results);
      setHydratedResult(null);
      setActiveTab("gates");
      loadBootstrap();
      setToast("Build complete — review safety gates");
    }
  }, [spliceJob.result, loadBootstrap]);

  useEffect(() => {
    if (!displayBuildDir) return;
    benchStatus(displayBuildDir).then(setBenchSession).catch(() => {});
  }, [displayBuildDir]);

  const refreshBench = useCallback(async () => {
    if (!displayBuildDir) return;
    const session = await benchStatus(displayBuildDir);
    setBenchSession(session);
    return session;
  }, [displayBuildDir]);

  const startBuild = async (intake, { exampleId } = {}) => {
    spliceJob.clearError();
    setHydratedResult(null);
    setView(VIEWS.results);
    setActiveTab("info");
    const jobId = await spliceJob.startBuild(intake, { exportGerber: false });
    setActiveJobId(jobId);
    if (exampleId) setSelectedExampleId(exampleId);
  };

  const loadJobResult = async (jobId) => {
    spliceJob.reset();
    const payload = await fetchJobResult(jobId);
    if (payload.ok && payload.result) {
      setHydratedResult(payload.result);
      setActiveJobId(jobId);
      setView(VIEWS.results);
      setActiveTab("gates");
      const dir = payload.result.build_dir || payload.result.project_package?.build_dir;
      if (dir) {
        const session = await benchStatus(dir);
        setBenchSession(session);
      }
    }
  };

  const handleQuickDemo = () => {
    const ex = examples.find((r) => r.id.includes("robot_drive_brief")) || examples[0];
    if (ex?.intake) startBuild(ex.intake, { exampleId: ex.id });
  };

  const handleBenchSubmit = async (measurements) => {
    if (!displayBuildDir) return;
    const session = await benchSubmit(displayBuildDir, measurements);
    setBenchSession(session);
    if (displayResult?.project_package?.gates) {
      const pkg = hydratedResult?.project_package || spliceJob.result?.project_package;
      if (pkg) {
        const updater = (prev) =>
          prev
            ? {
                ...prev,
                project_package: {
                  ...prev.project_package,
                  gates: {
                    ...prev.project_package.gates,
                    open_gate_count: session.open_gate_count,
                    critical_open_count: session.critical_open_count,
                    power_on_authorized: session.power_on_authorized,
                  },
                },
              }
            : prev;
        if (hydratedResult) setHydratedResult(updater);
      }
    }
  };

  const renderResults = () => {
    if (!displayPackage && !spliceJob.active) {
      return (
        <section className="card empty-card">
          <p className="muted">Select a build from the sidebar or start a new project.</p>
          {spliceJob.error && <p className="error">{spliceJob.error}</p>}
        </section>
      );
    }

    if (!displayPackage) return null;

    switch (activeTab) {
      case "info":
        return <InfoPanel pkg={displayPackage} />;
      case "bom":
        return <BomPanel pkg={displayPackage} />;
      case "wiring":
        return <WiringPanel pkg={displayPackage} />;
      case "instructions":
        return <InstructionsPanel pkg={displayPackage} />;
      case "design":
        return <DesignPreviewPanel buildDir={displayBuildDir} pkg={displayPackage} />;
      case "gates":
        return <GatesPanel pkg={displayPackage} benchSession={benchSession} />;
      case "bench":
        return (
          <BenchPanel
            buildDir={displayBuildDir}
            benchSession={benchSession}
            onRefresh={() => refreshBench()}
            onSubmit={handleBenchSubmit}
            onSuccess={setToast}
          />
        );
      default:
        return null;
    }
  };

  const inResults = view === VIEWS.results;

  return (
    <div className="app-shell">
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
          {[
            ["Home", VIEWS.home],
            ["New project", VIEWS.wizard],
            ["Examples", VIEWS.example],
            ["Interface lab", VIEWS.lab],
            ["Project", VIEWS.results],
          ].map(([label, id]) => (
            <button
              key={id}
              type="button"
              className={`nav-button ${view === id ? "active" : ""}`}
              onClick={() => setView(id)}
              disabled={id === VIEWS.results && !displayPackage && !spliceJob.active}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-section">
          <div className="sidebar-label">Engine</div>
          <StatusPill ok={health?.ok} label={health?.ok ? "Online" : "Offline"} />
          {loadError && (
            <button type="button" className="link-button small" onClick={loadBootstrap}>
              Retry connection
            </button>
          )}
        </div>

        {recentJobs.length > 0 && (
          <div className="sidebar-section sidebar-grow">
            <div className="sidebar-label">Recent builds</div>
            <div className="project-list">
              {recentJobs.slice(0, 10).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${activeJobId === job.job_id ? "active" : ""} ${jobStatusClass(job.status)}`}
                  onClick={() => job.status === "succeeded" && loadJobResult(job.job_id)}
                  disabled={job.status !== "succeeded"}
                  title={job.status}
                >
                  <strong>{job.project_name || job.job_id}</strong>
                  <span>{job.status}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </aside>

      <main className="main">
        {inResults && displayPackage && (
          <header className="project-header">
            <div className="project-header-text">
              <p className="eyebrow">Project package</p>
              <h1>{displayPackage.info?.project_name || "Your project"}</h1>
              <p className="muted">{displayPackage.info?.goal}</p>
            </div>
            <div className="project-header-actions">
              {activeJobId && (
                <a className="secondary button-link" href={jobBundleUrl(activeJobId)} download>
                  ↓ Download zip
                </a>
              )}
            </div>
          </header>
        )}

        {inResults && displayPackage && (
          <>
            <ProjectSummaryBar
              pkg={displayPackage}
              benchSession={benchSession}
              onGoBench={() => setActiveTab("bench")}
            />
            <TabNav
              tabs={PROJECT_TABS}
              activeId={activeTab}
              onChange={setActiveTab}
              badges={tabBadges}
            />
          </>
        )}

        <div className={`content ${inResults ? "content-results" : ""}`}>
          {view === VIEWS.home && (
            <HomeHero
              apiOk={health?.ok}
              version={health?.version}
              onStart={() => setView(VIEWS.wizard)}
              onExample={() => setView(VIEWS.example)}
              onQuickDemo={handleQuickDemo}
            />
          )}

          {view === VIEWS.wizard && (
            <ProjectWizard
              donorFixtures={donorFixtures}
              onCancel={() => setView(VIEWS.home)}
              onBuild={(intake) => startBuild(intake)}
              building={spliceJob.active}
              buildError={spliceJob.error}
              stageLabel={spliceJob.stageLabel}
            />
          )}

          {view === VIEWS.example && (
            <div className="example-shell">
              <section className="card">
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
                    onClick={() => selectedExample?.intake && startBuild(selectedExample.intake, { exampleId: selectedExample.id })}
                  >
                    Build selected example
                  </button>
                </div>
              </section>
            </div>
          )}

          {view === VIEWS.results && renderResults()}

          {view === VIEWS.lab && <InterfaceLabPanel />}
        </div>
      </main>
    </div>
  );
}
