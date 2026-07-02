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
import ProjectWizard from "./components/ProjectWizard.jsx";
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
};

function HomeHero({ onStart, onExample, apiOk }) {
  return (
    <section className="home-hero card">
      <p className="eyebrow">Hardware-Splicer</p>
      <h2>Turn junk parts into a buildable hardware project</h2>
      <p className="lead">
        Describe what you want in plain English. We compile a carrier board, parts list, wiring guide,
        and <strong>safety gates</strong> you must close before power-on.
      </p>
      <div className="hero-actions">
        <button type="button" className="primary large" onClick={onStart} disabled={!apiOk}>
          Start a project
        </button>
        <button type="button" className="ghost large" onClick={onExample} disabled={!apiOk}>
          Try an example
        </button>
      </div>
      {!apiOk && (
        <p className="error small">
          Start the backend first: <code>hs-serve --port 8787</code>
        </p>
      )}
      <ul className="hero-points">
        <li>Salvage motors &amp; drivers from dead gadgets</li>
        <li>KiCad carrier compile with honest DRC</li>
        <li>Bench checklist — no hand-wavy “should be fine”</li>
      </ul>
    </section>
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

  const spliceJob = useSpliceJob();
  const displayResult = spliceJob.result || hydratedResult;
  const displayPackage = displayResult?.project_package || null;
  const displayBuildDir = displayResult?.build_dir || displayPackage?.build_dir || null;

  const selectedExample = useMemo(
    () => examples.find((row) => row.id === selectedExampleId) || examples[0] || null,
    [examples, selectedExampleId],
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
    }
  }, [selectedExampleId]);

  useEffect(() => {
    loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (spliceJob.result && view === VIEWS.wizard) {
      setView(VIEWS.results);
      setHydratedResult(null);
      loadBootstrap();
    }
  }, [spliceJob.result, view, loadBootstrap]);

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

  const loadJobResult = async (jobId) => {
    spliceJob.reset();
    const payload = await fetchJobResult(jobId);
    if (payload.ok && payload.result) {
      setHydratedResult(payload.result);
      setActiveJobId(jobId);
      setView(VIEWS.results);
      const dir = payload.result.build_dir || payload.result.project_package?.build_dir;
      if (dir) {
        const session = await benchStatus(dir);
        setBenchSession(session);
      }
    }
  };

  const handleWizardBuild = async (intake) => {
    const jobId = await spliceJob.startBuild(intake, { exportGerber: false });
    setActiveJobId(jobId);
    setHydratedResult(null);
  };

  const handleExampleBuild = async () => {
    if (!selectedExample?.intake) return;
    setHydratedResult(null);
    const jobId = await spliceJob.startBuild(selectedExample.intake, { exportGerber: false });
    setActiveJobId(jobId);
    setView(VIEWS.results);
  };

  const handleBenchSubmit = async (measurements) => {
    const dir = displayBuildDir;
    if (!dir) return;
    const session = await benchSubmit(dir, measurements);
    setBenchSession(session);
  };

  const renderResults = () => {
    const pkg = displayPackage;
    if (!pkg) {
      return (
        <section className="card empty-state">
          {spliceJob.active ? (
            <div className="build-progress">
              <div className="spinner" aria-hidden />
              <p>{spliceJob.stageLabel || "Building…"}</p>
            </div>
          ) : (
            <p className="muted">No project loaded.</p>
          )}
          {spliceJob.error && <p className="error">{spliceJob.error}</p>}
        </section>
      );
    }

    switch (activeTab) {
      case "info":
        return <InfoPanel pkg={pkg} />;
      case "bom":
        return <BomPanel pkg={pkg} />;
      case "wiring":
        return <WiringPanel pkg={pkg} />;
      case "instructions":
        return <InstructionsPanel pkg={pkg} />;
      case "gates":
        return <GatesPanel pkg={pkg} benchSession={benchSession} />;
      case "bench":
        return (
          <BenchPanel
            buildDir={displayBuildDir}
            benchSession={benchSession}
            onRefresh={() => refreshBench()}
            onSubmit={handleBenchSubmit}
          />
        );
      default:
        return null;
    }
  };

  const showResultsChrome = view === VIEWS.results && (displayPackage || spliceJob.active);

  return (
    <div className="app-shell consumer">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">HS</div>
          <div>
            <strong>Hardware-Splicer</strong>
            <span>Build from salvage</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <button
            type="button"
            className={`nav-button ${view === VIEWS.home ? "active" : ""}`}
            onClick={() => setView(VIEWS.home)}
          >
            Home
          </button>
          <button
            type="button"
            className={`nav-button ${view === VIEWS.wizard ? "active" : ""}`}
            onClick={() => setView(VIEWS.wizard)}
          >
            New project
          </button>
          <button
            type="button"
            className={`nav-button ${view === VIEWS.example ? "active" : ""}`}
            onClick={() => setView(VIEWS.example)}
          >
            Examples
          </button>
        </nav>

        <div className="sidebar-section">
          <div className="sidebar-label">Status</div>
          <StatusPill ok={health?.ok} label={health?.ok ? "Ready" : "Offline"} />
          {loadError && <p className="error small">{loadError}</p>}
        </div>

        {recentJobs.length > 0 && (
          <div className="sidebar-section">
            <div className="sidebar-label">Recent builds</div>
            <div className="project-list">
              {recentJobs.slice(0, 8).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${activeJobId === job.job_id ? "active" : ""}`}
                  onClick={() => job.status === "succeeded" && loadJobResult(job.job_id)}
                  disabled={job.status !== "succeeded"}
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
        {showResultsChrome && (
          <header className="topbar">
            <div>
              <h1>{displayPackage?.info?.project_name || "Your project"}</h1>
              <p className="muted">{displayPackage?.info?.goal || ""}</p>
            </div>
            <div className="topbar-actions">
              {activeJobId && (
                <a className="ghost button-link" href={jobBundleUrl(activeJobId)}>
                  Download zip
                </a>
              )}
              <div className="tab-bar">
                {PROJECT_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={activeTab === tab.id ? "active" : ""}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          </header>
        )}

        <div className="content">
          {view === VIEWS.home && (
            <HomeHero
              apiOk={health?.ok}
              onStart={() => setView(VIEWS.wizard)}
              onExample={() => setView(VIEWS.example)}
            />
          )}

          {view === VIEWS.wizard && (
            <ProjectWizard
              donorFixtures={donorFixtures}
              onCancel={() => setView(VIEWS.home)}
              onBuild={handleWizardBuild}
              building={spliceJob.active}
              buildError={spliceJob.error}
              stageLabel={spliceJob.stageLabel}
            />
          )}

          {view === VIEWS.example && (
            <div className="example-shell">
              <section className="card">
                <h2>Try a ready-made project</h2>
                <p className="muted">Same flow as a custom project — useful for demos and learning the gates.</p>
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
                    onClick={handleExampleBuild}
                  >
                    {spliceJob.active ? spliceJob.stageLabel || "Building…" : "Build this example"}
                  </button>
                </div>
                {spliceJob.error && <p className="error">{spliceJob.error}</p>}
              </section>
            </div>
          )}

          {view === VIEWS.results && renderResults()}
        </div>
      </main>
    </div>
  );
}
