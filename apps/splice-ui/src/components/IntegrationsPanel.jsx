import { useEffect, useState } from "react";
import { downloadBuildArtifact, fetchFabManifest, fetchIntegrationsCatalog } from "../api.js";

const FAB_STATUS_LABEL = {
  present: "Present",
  missing: "Missing",
  optional: "Optional",
  planned: "Planned",
};

const FAB_STATUS_CLASS = {
  present: "present",
  missing: "missing",
  optional: "optional",
  planned: "planned",
};

const STATUS_LABEL = {
  wired: "Wired",
  core: "Core",
  opt_in: "Opt-in",
  partial: "Partial",
  documented: "Documented",
  reference: "Reference",
  planned: "Planned",
};

const STATUS_CLASS = {
  wired: "status-wired",
  core: "status-core",
  opt_in: "status-opt-in",
  partial: "status-partial",
  documented: "status-documented",
  reference: "status-reference",
  planned: "status-planned",
};

export default function IntegrationsCatalog() {
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchIntegrationsCatalog()
      .then(setCatalog)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    const staleApi = /not found/i.test(error);
    return (
      <section className="card integration-catalog-fallback">
        <h3>4 · OSS integration map</h3>
        {staleApi ? (
          <>
            <p className="muted">
              Integration catalog unavailable — restart the API server on port 8787 with the current codebase.
            </p>
            <p className="mono small muted">GET /v1/integrations/catalog → {error}</p>
          </>
        ) : (
          <p className="error">{error}</p>
        )}
      </section>
    );
  }
  if (!catalog) return <p className="muted">Loading OSS integration map…</p>;

  return (
    <section className="card">
      <h3>4 · OSS integration map</h3>
      <p className="muted">{catalog.thesis}</p>
      <p className="chip">
        {catalog.wired_count} wired / {catalog.total_count} catalogued
      </p>
      <div className="integration-grid">
        {catalog.integrations.map((row) => (
          <article key={row.id} className={`integration-card ${STATUS_CLASS[row.status] || ""}`}>
            <div className="integration-card-head">
              <strong>
                <a href={row.url} target="_blank" rel="noreferrer">
                  {row.name}
                </a>
              </strong>
              <span className={`integration-status ${STATUS_CLASS[row.status] || ""}`}>
                {STATUS_LABEL[row.status] || row.status}
              </span>
            </div>
            <p className="muted small">{row.claim}</p>
            <p className="mono small integration-hook">{row.hook}</p>
            <p className="muted small">
              {row.layer} · {row.license} · {row.priority}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function DesignArtifactsPanel({ buildDir }) {
  const [artifacts, setArtifacts] = useState([]);
  const [circuitJson, setCircuitJson] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [autorouteMsg, setAutorouteMsg] = useState("");

  useEffect(() => {
    if (!buildDir) return;
    import("../api.js").then(({ listBuildArtifacts, exportCircuitJson }) => {
      listBuildArtifacts(buildDir)
        .then((payload) => setArtifacts(payload.artifacts || []))
        .catch((err) => setError(err.message));
      exportCircuitJson(buildDir)
        .then((payload) => setCircuitJson(payload.circuit_json))
        .catch(() => setCircuitJson(null));
    });
  }, [buildDir]);

  if (!buildDir) return null;

  const handleDownload = async (relative) => {
    setBusy(relative);
    setError("");
    try {
      await downloadBuildArtifact(buildDir, relative);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const handleAutoroute = async () => {
    setBusy("autoroute");
    setAutorouteMsg("");
    setError("");
    try {
      const { runBuildAutoroute } = await import("../api.js");
      const result = await runBuildAutoroute(buildDir);
      setAutorouteMsg(
        result.autoroute?.ok
          ? "FreeRouting pass completed — refresh preview if PCB updated."
          : result.autoroute?.reason || result.autoroute?.skipped
            ? `Skipped: ${result.autoroute.reason || "unavailable"}`
            : "Autoroute finished with review required.",
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="card">
      <h3>Exports & interchange</h3>
      <p className="muted">
        Step 4 — Handoff: download compile artifacts for KiCad, circuit-json tools, fab upload, or agent pipelines.
      </p>
      {error && <p className="error">{error}</p>}
      {artifacts.length === 0 ? (
        <p className="muted">No export artifacts found for this build yet.</p>
      ) : (
        <ul className="artifact-list">
          {artifacts.map((row) => (
            <li key={row.relative}>
              <div>
                <strong>{row.label}</strong>
                <span className="muted small mono"> {row.relative}</span>
              </div>
              <button
                type="button"
                className="secondary small"
                disabled={busy === row.relative}
                onClick={() => handleDownload(row.relative)}
              >
                {busy === row.relative ? "…" : "Download"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {circuitJson && (
        <details className="circuit-json-preview">
          <summary>circuit-json preview ({circuitJson.length} docs)</summary>
          <pre className="lab-output">{JSON.stringify(circuitJson.slice(0, 8), null, 2)}…</pre>
        </details>
      )}
      <div className="lab-actions">
        <button
          type="button"
          className="ghost small"
          disabled={Boolean(busy)}
          onClick={handleAutoroute}
          title="Opt-in GPL FreeRouting — carrier boards only"
        >
          {busy === "autoroute" ? "Routing…" : "Run opt-in FreeRouting"}
        </button>
      </div>
      {autorouteMsg && <p className="muted small">{autorouteMsg}</p>}
    </section>
  );
}

export function DesignReadinessPanel({ buildDir, onRecheckComplete }) {
  const [recheckMsg, setRecheckMsg] = useState("");
  const [recheckBusy, setRecheckBusy] = useState(false);

  const handleRecheck = async () => {
    setRecheckBusy(true);
    setRecheckMsg("");
    try {
      const { recheckBuildAfterKicad } = await import("../api.js");
      const result = await recheckBuildAfterKicad(buildDir);
      const drc = result.drc || {};
      setRecheckMsg(
        drc.skipped
          ? `Recheck skipped: ${drc.reason || "kicad-cli unavailable"}`
          : drc.pass
            ? `KiCad recheck OK — ${drc.errors ?? 0} DRC errors, ${drc.warnings ?? 0} warnings.`
            : `KiCad recheck: ${drc.errors ?? "?"} DRC errors — review before bench.`,
      );
      onRecheckComplete?.(result);
    } catch (err) {
      setRecheckMsg(err.message);
    } finally {
      setRecheckBusy(false);
    }
  };

  return (
    <section className="card design-readiness-card">
      <h3>Design readiness</h3>
      <p className="muted">
        Inspect the compile BOM and fab artifact coverage before handoff. After editing in KiCad, recheck DRC/ERC here.
      </p>
      <div className="lab-actions">
        <button type="button" className="secondary small" disabled={recheckBusy} onClick={handleRecheck}>
          {recheckBusy ? "Rechecking…" : "Recheck after KiCad edit"}
        </button>
      </div>
      {recheckMsg && <p className="muted small">{recheckMsg}</p>}
      <DesignBomPanel buildDir={buildDir} />
      <FabManifestPanel buildDir={buildDir} />
      <HumanViewsPanel buildDir={buildDir} />
    </section>
  );
}

export function DesignBomPanel({ buildDir }) {
  const [bom, setBom] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!buildDir) return;
    import("../api.js")
      .then(({ fetchBuildBom }) => fetchBuildBom(buildDir))
      .then(setBom)
      .catch((err) => setError(err.message));
  }, [buildDir]);

  if (!buildDir || error) {
    if (error && !error.includes("no BOM")) {
      return <p className="muted small">{error}</p>;
    }
    if (error) {
      return (
        <div className="design-bom-panel">
          <h4>Compile BOM</h4>
          <p className="muted small">No compile BOM for this build yet — run a full compile with BOM emission.</p>
        </div>
      );
    }
    return null;
  }
  if (!bom) return <p className="muted small">Loading compile BOM…</p>;
  const lines = bom.lines || [];
  const hasJlc = lines.some((row) => row.jlc_lcsc || row.jlc_mpn);

  return (
    <div className="design-bom-panel">
      <h4>Compile BOM</h4>
      <p className="muted small">
        {bom.line_count} lines from {bom.source}
        {bom.jlc_enriched || hasJlc
          ? " · JLC/LCSC hints present"
          : " · sourcing hints optional (not required for preview)"}
      </p>
      {lines.length === 0 ? (
        <p className="muted">No BOM lines.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table compact">
            <thead>
              <tr>
                <th>Ref</th>
                <th>Description</th>
                <th>Qty</th>
                {hasJlc && <th>LCSC</th>}
              </tr>
            </thead>
            <tbody>
              {lines.slice(0, 24).map((row, index) => (
                <tr key={`${row.ref || row.module_id}-${index}`}>
                  <td className="mono">{row.ref || row.module_id || "—"}</td>
                  <td>{row.description || row.module_id || "—"}</td>
                  <td>{row.qty ?? 1}</td>
                  {hasJlc && <td className="mono small">{row.jlc_lcsc || "—"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function FabManifestPanel({ buildDir }) {
  const [manifest, setManifest] = useState(null);

  useEffect(() => {
    if (!buildDir) return;
    fetchFabManifest(buildDir)
      .then(setManifest)
      .catch(() => setManifest(null));
  }, [buildDir]);

  if (!buildDir || !manifest) return null;

  const requiredMissing = manifest.artifacts.filter(
    (row) => row.status === "missing" && !row.optional && !row.planned,
  );

  return (
    <details className="fab-manifest-panel" open={requiredMissing.length > 0}>
      <summary>
        Fab artifact coverage — {manifest.present_count} required present
        {manifest.optional_present_count ? `, ${manifest.optional_present_count} optional` : ""}
      </summary>
      <p className="muted small">{manifest.note}</p>
      <ul className="fab-manifest-list">
        {manifest.artifacts.map((row) => (
          <li key={row.id} className={`fab-status-${row.status || (row.present ? "present" : "missing")}`}>
            <span>
              {row.label}
              {row.optional_note && !row.present && (
                <span className="muted small"> — {row.optional_note}</span>
              )}
            </span>
            <span className="chip small">
              {row.status === "present"
                ? "present"
                : row.status === "optional"
                  ? "optional"
                  : row.status === "planned"
                    ? "planned"
                    : "missing"}
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

const VIEW_STATUS_LABEL = { present: "ready", skipped: "skipped", missing: "missing" };

export function HumanViewsPanel({ buildDir }) {
  const [views, setViews] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadViews = async (generate = false) => {
    setBusy(true);
    setError("");
    try {
      const { exportBuildViews, listBuildArtifacts } = await import("../api.js");
      if (generate) {
        const result = await exportBuildViews(buildDir);
        if (!result.ok && result.skipped) {
          setError(result.reason || "kicad-cli export unavailable");
        }
      }
      const artifacts = await listBuildArtifacts(buildDir);
      const human = (artifacts.artifacts || []).filter((row) => row.kind === "human_view");
      setViews(human);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (buildDir) loadViews(false);
  }, [buildDir]);

  if (!buildDir) return null;

  return (
    <div className="human-views-panel">
      <h4>Human-readable exports</h4>
      <p className="muted small">PDF/SVG/PNG via kicad-cli — for reviewers without KiCanvas or KiCad installed.</p>
      <div className="lab-actions">
        <button type="button" className="secondary small" disabled={busy} onClick={() => loadViews(true)}>
          {busy ? "Exporting…" : "Generate PDF/SVG views"}
        </button>
      </div>
      {error && <p className="muted small">{error}</p>}
      {views && views.length > 0 && (
        <ul className="artifact-list compact">
          {views.map((row) => (
            <li key={row.relative}>
              <span className="mono small">{row.name}</span>
              <button
                type="button"
                className="ghost small"
                onClick={() => downloadBuildArtifact(buildDir, row.relative)}
              >
                Download
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
