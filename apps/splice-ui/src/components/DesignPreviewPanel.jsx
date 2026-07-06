import { useEffect, useRef, useState } from "react";
import { fetchBuildFileContent, listBuildFiles } from "../api.js";

function useKiCanvasScript() {
  const [ready, setReady] = useState(
    () => typeof customElements !== "undefined" && Boolean(customElements.get("kicanvas-embed")),
  );

  useEffect(() => {
    if (ready) return undefined;
    const existing = document.querySelector('script[data-kicanvas="1"]');
    if (existing) {
      existing.addEventListener("load", () => setReady(true), { once: true });
      return undefined;
    }
    const script = document.createElement("script");
    script.type = "module";
    script.src = "/kicanvas/kicanvas.js";
    script.dataset.kicanvas = "1";
    script.onload = () => setReady(true);
    script.onerror = () => setReady(false);
    document.head.appendChild(script);
    return () => {};
  }, [ready]);

  return ready;
}

function KiCanvasInline({ content, label }) {
  const hostRef = useRef(null);
  const kicanvasReady = useKiCanvasScript();

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !kicanvasReady || !content) return;
    host.replaceChildren();
    const embed = document.createElement("kicanvas-embed");
    embed.setAttribute("controls", "basic");
    embed.setAttribute("controlslist", "nodownload");
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
        {!kicanvasReady && <span className="muted">Loading KiCanvas viewer…</span>}
      </div>
      <div ref={hostRef} className="kicanvas-host" />
    </div>
  );
}

export default function DesignPreviewPanel({ buildDir, pkg }) {
  const [files, setFiles] = useState([]);
  const [activeRelative, setActiveRelative] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    if (!buildDir || !activeRelative) {
      setContent("");
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetchBuildFileContent(buildDir, activeRelative)
      .then((payload) => {
        if (!cancelled) setContent(payload.content || "");
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [buildDir, activeRelative]);

  const drc = pkg?.gates?.design_quality_gate || pkg?.gates || {};

  return (
    <div className="panel-stack">
      <section className="card">
        <h3>Design preview</h3>
        <p className="muted">
          Read-only KiCad preview via embedded{" "}
          <a href="https://kicanvas.org/" target="_blank" rel="noreferrer">
            KiCanvas
          </a>
          . Proves the engine emits inspectable ECAD artifacts.
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
          !error && <p className="muted">No `.kicad_pcb` / `.kicad_sch` files found in this build.</p>
        )}
        {loading ? <p className="muted">Loading KiCad file…</p> : <KiCanvasInline content={content} label={activeRelative} />}
      </section>
      <section className="card">
        <h3>Compile truth</h3>
        <dl className="meta-grid">
          <div>
            <dt>DRC errors</dt>
            <dd>{drc.kicad_drc_errors ?? drc.compile_errors ?? "—"}</dd>
          </div>
          <div>
            <dt>DRC warnings</dt>
            <dd>{drc.kicad_drc_warnings ?? "—"}</dd>
          </div>
          <div>
            <dt>Copper tier</dt>
            <dd>{drc.copper_tier || "—"}</dd>
          </div>
          <div>
            <dt>Fab recommendation</dt>
            <dd>{drc.fab_recommendation || "—"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
