import { useEffect, useRef, useState } from "react";
import { fetchBuildFileContent, fetchDesignQuality, listBuildFiles } from "../api.js";
import {
  compileTruthHeadline,
  copperTierLabel,
  normalizeCompileTruth,
} from "../utils/compileTruth.js";
import { StatusPill } from "./ProjectPanels.jsx";
import DesignFlowStepper from "./DesignFlowStepper.jsx";
import { DesignArtifactsPanel, DesignReadinessPanel } from "./IntegrationsPanel.jsx";

function useKiCanvasScript() {
  const [ready, setReady] = useState(
    () => typeof customElements !== "undefined" && Boolean(customElements.get("kicanvas-embed")),
  );
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (ready) return undefined;
    const existing = document.querySelector('script[data-kicanvas="1"]');
    if (existing) {
      existing.addEventListener("load", () => setReady(true), { once: true });
      existing.addEventListener("error", () => setFailed(true), { once: true });
      return undefined;
    }
    const script = document.createElement("script");
    script.type = "module";
    script.src = "/kicanvas/kicanvas.js";
    script.dataset.kicanvas = "1";
    script.onload = () => setReady(true);
    script.onerror = () => setFailed(true);
    document.head.appendChild(script);
    return () => {};
  }, [ready]);

  return { ready, failed };
}

function KiCanvasInline({ content, label }) {
  const hostRef = useRef(null);
  const { ready: kicanvasReady, failed: kicanvasFailed } = useKiCanvasScript();

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !kicanvasReady || !content) return;
    host.replaceChildren();
    const embed = document.createElement("kicanvas-embed");
    embed.setAttribute("controls", "basic");
    embed.setAttribute("controlslist", "nodownload nooverlay");
    const source = document.createElement("kicanvas-source");
    source.textContent = content;
    embed.appendChild(source);
    host.appendChild(embed);
  }, [kicanvasReady, content]);

  if (!content) {
    return <p className="muted">No KiCad document loaded.</p>;
  }

  return (
    <div className="kicanvas-panel">
      <div className="kicanvas-toolbar">
        <span className="chip">{label}</span>
        {!kicanvasReady && !kicanvasFailed && <span className="muted">Loading KiCanvas viewer…</span>}
        {kicanvasFailed && <span className="error">KiCanvas failed to load — refresh or check /kicanvas/kicanvas.js</span>}
      </div>
      <p className="muted small kicanvas-hint">Click the board to pan and zoom. Read-only preview — edit in KiCad if needed.</p>
      <div ref={hostRef} className="kicanvas-host" />
    </div>
  );
}

function CompileTruthCard({ truth, loading }) {
  if (loading) return <p className="muted">Loading compile truth from build artifacts…</p>;
  if (!truth) return <p className="muted">No compile metadata found for this build.</p>;

  const ok = truth.compile_ok !== false && (truth.kicad_drc_errors ?? 0) === 0;

  return (
    <>
      <div className="design-truth-head">
        <StatusPill ok={ok} label={ok ? "KiCad truth OK" : "Review required"} />
        <p className="muted small">{compileTruthHeadline(truth)}</p>
      </div>
      <dl className="meta-grid">
        <div>
          <dt>DRC errors</dt>
          <dd>{truth.kicad_drc_errors ?? "—"}</dd>
        </div>
        <div>
          <dt>DRC warnings</dt>
          <dd>{truth.kicad_drc_warnings ?? "—"}</dd>
        </div>
        <div>
          <dt>Copper tier</dt>
          <dd>{copperTierLabel(truth.copper_tier)}</dd>
        </div>
        <div>
          <dt>Fab recommendation</dt>
          <dd>{truth.fab_recommendation ? String(truth.fab_recommendation).replace(/_/g, " ") : "—"}</dd>
        </div>
      </dl>
    </>
  );
}

export default function DesignPreviewPanel({ buildDir, pkg, qualityHint, title, onGoGates }) {
  const [files, setFiles] = useState([]);
  const [activeRelative, setActiveRelative] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [loadingFile, setLoadingFile] = useState(false);
  const [quality, setQuality] = useState(null);
  const [loadingQuality, setLoadingQuality] = useState(false);

  const reloadQuality = () => {
    if (!buildDir) return;
    setLoadingQuality(true);
    fetchDesignQuality(buildDir)
      .then(setQuality)
      .catch(() => setQuality(qualityHint || normalizeCompileTruth({ pkg })))
      .finally(() => setLoadingQuality(false));
  };

  const truth = normalizeCompileTruth({ pkg, quality: quality || qualityHint });

  useEffect(() => {
    if (!buildDir) return;
    let cancelled = false;
    setError("");
    listBuildFiles(buildDir)
      .then((payload) => {
        if (cancelled) return;
        const rows = payload.files || [];
        setFiles(rows);
        const preferred =
          rows.find((row) => row.kind === "pcb") ||
          rows.find((row) => row.kind === "schematic") ||
          rows[0];
        if (preferred) setActiveRelative(preferred.relative);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [buildDir]);

  useEffect(() => {
    if (!buildDir) {
      setQuality(qualityHint || null);
      return;
    }
    if (qualityHint && !pkg) {
      setQuality(qualityHint);
    }
    let cancelled = false;
    setLoadingQuality(true);
    fetchDesignQuality(buildDir)
      .then((payload) => {
        if (!cancelled) setQuality(payload);
      })
      .catch(() => {
        if (!cancelled) setQuality(qualityHint || normalizeCompileTruth({ pkg }));
      })
      .finally(() => {
        if (!cancelled) setLoadingQuality(false);
      });
    return () => {
      cancelled = true;
    };
  }, [buildDir, pkg, qualityHint]);

  useEffect(() => {
    if (!buildDir || !activeRelative) {
      setContent("");
      return undefined;
    }
    let cancelled = false;
    setLoadingFile(true);
    setError("");
    fetchBuildFileContent(buildDir, activeRelative)
      .then((payload) => {
        if (!cancelled) setContent(payload.content || "");
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoadingFile(false);
      });
    return () => {
      cancelled = true;
    };
  }, [buildDir, activeRelative]);

  if (!buildDir) {
    return (
      <section className="card empty-card">
        <p className="muted">No build directory available. Run a project build or Interface lab compile first.</p>
      </section>
    );
  }

  return (
    <div className="panel-stack">
      <DesignFlowStepper active="visual" />
      {title && (
        <section className="card design-preview-banner">
          <p className="eyebrow">KiCad preview</p>
          <h3>{title}</h3>
        </section>
      )}
      <section className="card">
        <h3>Board & schematic</h3>
        <p className="muted">
          Step 1 — Visual: inspect the KiCad carrier in{" "}
          <a href="https://kicanvas.org/" target="_blank" rel="noreferrer">
            KiCanvas
          </a>{" "}
          (read-only; edit in KiCad if needed).
        </p>
        {error && <p className="error">{error}</p>}
        {files.length > 0 ? (
          <div className="file-picker-row">
            {files.map((file) => (
              <button
                key={file.relative}
                type="button"
                className={`chip-button ${activeRelative === file.relative ? "active" : ""}`}
                onClick={() => setActiveRelative(file.relative)}
              >
                {file.name}
              </button>
            ))}
          </div>
        ) : (
          !error && <p className="muted">No `.kicad_pcb` / `.kicad_sch` files found in this build yet.</p>
        )}
        {loadingFile ? (
          <p className="muted">Loading KiCad file…</p>
        ) : (
          <KiCanvasInline content={content} label={activeRelative} />
        )}
      </section>
      <section className="card">
        <h3>Compile truth</h3>
        <p className="muted small">Step 2 — Authority: KiCad DRC and design-quality artifacts from the engine.</p>
        <CompileTruthCard truth={truth} loading={loadingQuality} />
        {onGoGates && pkg?.gates && (
          <button type="button" className="secondary small design-gates-link" onClick={onGoGates}>
            Continue to Bench →
          </button>
        )}
      </section>
      <DesignReadinessPanel buildDir={buildDir} onRecheckComplete={reloadQuality} />
      <DesignArtifactsPanel buildDir={buildDir} />
    </div>
  );
}
