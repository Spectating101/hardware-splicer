import { useCallback, useEffect, useMemo, useState } from "react";
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
  jobBundleUrl,
} from "./api.js";
import AiAssistPanel from "./components/AiAssistPanel.jsx";
import BuildOverlay from "./components/BuildOverlay.jsx";
import DesignPreviewPanel from "./components/DesignPreviewPanel.jsx";
import InterfaceLabPanel from "./components/InterfaceLabPanel.jsx";
import PipelineVisual from "./components/PipelineVisual.jsx";
import ProjectSummaryBar from "./components/ProjectSummaryBar.jsx";
import ReadinessHero from "./components/ReadinessHero.jsx";
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
  preview: "preview",
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

function formatProjectName(name) {
  if (!name) return "Untitled build";
  return name.replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

function formatJobStatus(status) {
  if (!status) return "Unknown";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function HomeHero({ onStart, onExample, onQuickDemo, apiOk, version }) {
  return (
    <div className="home-layout">
      <section className="home-hero card">
        <p className="eyebrow">Hardware-Splicer · Splice Agent {version ? `v${version}` : ""}</p>
        <h1>Design PCBs with AI — plus auditable bring-up Flux doesn’t ship</h1>
        <p className="lead">
          <strong>AI carrier design</strong> (describe → compose → KiCad) or <strong>salvage splice</strong> (donor
          vision → gates → bench capture) — browser workbench with honest DRC, LCSC-aware BOM, and{" "}
          <code>PROJECT_PACKAGE</code> handoff.
        </p>
        <div className="readiness-pitch">
          <strong>Flux-class first mile. Hardware-Splicer last mile.</strong>
          <p className="muted small">
            Compete on NL → board like Flux, then win on compile truth, measurement gates, and defensible packages —
            self-hosted, not credit-metered black box.
          </p>
        </div>
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

export default function App() {
  const [health, setHealth] = useState(null);
  const [examples, setExamples] = useState([]);
  const [donorFixtures, setDonorFixtures] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [visionCapabilities, setVisionCapabilities] = useState(null);
  const [view, setView] = useState(VIEWS.home);
  const [selectedExampleId, setSelectedExampleId] = useState(null);
  const [activeTab, setActiveTab] = useState("info");
  const [benchSession, setBenchSession] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [activeJobId, setActiveJobId] = useState(null);
  const [hydratedResult, setHydratedResult] = useState(null);
  const [toast, setToast] = useState("");
  const [previewContext, setPreviewContext] = useState(null);

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

  const displayResult = spliceJob.result || hydratedResult;
  const displayPackage = displayResult?.project_package || null;
  const projectBuildDir = displayResult?.build_dir || displayPackage?.build_dir || null;
  const displayBuildDir =
    view === VIEWS.preview ? previewContext?.buildDir || projectBuildDir : projectBuildDir;
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
    if (spliceJob.result) {
      setPreviewContext(null);
      setView(VIEWS.results);
      setHydratedResult(null);
      setActiveTab(spliceJob.jobKind === "compose" ? "design" : "design");
      if (spliceJob.result.bench_session) {
        setBenchSession(spliceJob.result.bench_session);
      }
      loadBootstrap();
      setToast(
        spliceJob.jobKind === "compose"
          ? "AI compose complete — review KiCad carrier, BOM, and fab readiness"
          : "Build complete — review the KiCad carrier, then close bench gates",
      );
    }
  }, [spliceJob.result, spliceJob.jobKind, loadBootstrap]);

  useEffect(() => {
    if (!projectBuildDir) return;
    benchStatus(projectBuildDir).then(setBenchSession).catch(() => {});
  }, [projectBuildDir]);

  const refreshBench = useCallback(async () => {
    if (!projectBuildDir) return;
    const session = await benchStatus(projectBuildDir);
    setBenchSession(session);
    return session;
  }, [projectBuildDir]);

  const startBuild = async (payload, { exampleId, route = "splice" } = {}) => {
    spliceJob.clearError();
    setHydratedResult(null);
    setPreviewContext(null);
    setView(VIEWS.results);
    setActiveTab(route === "compose" ? "design" : "info");
    const jobId =
      route === "compose"
        ? await spliceJob.startCompose(payload, { exportGerber: false })
        : await spliceJob.startBuild(payload, { exportGerber: false });
    setActiveJobId(jobId);
    if (exampleId) setSelectedExampleId(exampleId);
  };

  const loadJobResult = async (jobId) => {
    spliceJob.reset();
    setPreviewContext(null);
    const payload = await fetchJobResult(jobId);
    if (payload.ok && payload.result) {
      setHydratedResult(payload.result);
      setActiveJobId(jobId);
      setView(VIEWS.results);
      setActiveTab("design");
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
    if (ex?.intake) startBuild(ex.intake, { exampleId: ex.id });
  };

  const handleBenchSubmit = async (measurements) => {
    if (!projectBuildDir) return;
    const session = await benchSubmit(projectBuildDir, measurements);
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
    return session;
  };

  const handleBenchCaptureSubmit = async (capture) => {
    if (!projectBuildDir) return null;
    const result = await benchSubmitCapture(projectBuildDir, capture);
    if (result?.bench_session) {
      setBenchSession(result.bench_session);
    }
    if (displayResult?.project_package?.gates && result?.bench_session) {
      const session = result.bench_session;
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
    return result;
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
      case "ai":
        return (
          <AiAssistPanel
            capabilities={visionCapabilities}
            donorVisionReport={displayResult?.donor_board_vision_report}
            visionEnrichReport={displayResult?.vision_evidence_report}
            clarifier={displayPackage.info?.clarifier}
          />
        );
      case "info":
        return <InfoPanel pkg={displayPackage} />;
      case "bom":
        return <BomPanel pkg={displayPackage} />;
      case "wiring":
        return <WiringPanel pkg={displayPackage} />;
      case "instructions":
        return <InstructionsPanel pkg={displayPackage} />;
      case "design":
        return (
          <DesignPreviewPanel
            buildDir={projectBuildDir}
            pkg={displayPackage}
            onGoGates={() => setActiveTab("gates")}
          />
        );
      case "gates":
        return <GatesPanel pkg={displayPackage} benchSession={benchSession} />;
      case "bench":
        return (
          <BenchPanel
            buildDir={projectBuildDir}
            benchSession={benchSession}
            onRefresh={() => refreshBench()}
            onSubmit={handleBenchSubmit}
            onSubmitCapture={handleBenchCaptureSubmit}
            onSuccess={setToast}
          />
        );
      default:
        return null;
    }
  };

  const inResults = view === VIEWS.results;
  const inPreview = view === VIEWS.preview;

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

        {uniqueRecentJobs.length > 0 && (
          <div className="sidebar-section sidebar-grow">
            <div className="sidebar-label">Recent builds</div>
            <div className="project-list">
              {uniqueRecentJobs.slice(0, 8).map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  className={`project-button ${activeJobId === job.job_id ? "active" : ""} ${jobStatusClass(job.status)}`}
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
        {inResults && displayPackage && (
          <header className="project-header">
            <div className="project-header-text">
              <p className="eyebrow">Project package</p>
              <h1>{displayPackage.info?.project_name || "Your project"}</h1>
              <p className="muted">{displayPackage.info?.goal}</p>
            </div>
            <div className="project-header-actions">
              {activeJobId && (
                <>
                  <button
                    type="button"
                    className="ghost button-link"
                    onClick={() => {
                      navigator.clipboard?.writeText(jobBundleUrl(activeJobId));
                      setToast("Share link copied — download bundle for reviewers");
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
        )}

        {inResults && displayPackage && (
          <>
            <ReadinessHero
              pkg={displayPackage}
              benchSession={benchSession}
              onGoDesign={() => setActiveTab("design")}
              onGoBench={() => setActiveTab("bench")}
              onGoGates={() => setActiveTab("gates")}
            />
            <ProjectSummaryBar
              pkg={displayPackage}
              benchSession={benchSession}
              onGoBench={() => setActiveTab("bench")}
              onGoDesign={() => setActiveTab("design")}
            />
            <TabNav
              tabs={PROJECT_TABS}
              activeId={activeTab}
              onChange={setActiveTab}
              badges={tabBadges}
            />
          </>
        )}

        <div className={`content ${inResults || inPreview ? "content-results" : ""}`}>
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
              visionCapabilities={visionCapabilities}
              llmPolicy={health?.llm_policy}
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

          {view === VIEWS.preview && (
            <div className="preview-shell">
              <div className="preview-toolbar card">
                <button type="button" className="ghost" onClick={() => setView(VIEWS.lab)}>
                  ← Back to Interface lab
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setPreviewContext(null);
                    setView(displayPackage ? VIEWS.results : VIEWS.home);
                  }}
                >
                  {displayPackage ? "Open full project" : "Home"}
                </button>
              </div>
              <DesignPreviewPanel
                buildDir={previewContext?.buildDir || displayBuildDir}
                qualityHint={previewContext?.qualityHint}
                title={previewContext?.title}
                onGoGates={displayPackage ? () => {
                  setPreviewContext(null);
                  setView(VIEWS.results);
                  setActiveTab("gates");
                } : null}
              />
            </div>
          )}

          {view === VIEWS.lab && (
            <InterfaceLabPanel
              llmPolicy={health?.llm_policy}
              onOpenDesignPreview={openDesignPreview}
              onRunFullDemo={handleRunRepairCafeDemo}
            />
          )}
        </div>
      </main>
    </div>
  );
}
