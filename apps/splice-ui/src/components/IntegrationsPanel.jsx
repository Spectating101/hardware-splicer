import { useEffect, useState } from "react";
import { downloadBuildArtifact, fetchIntegrationsCatalog } from "../api.js";

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

  if (error) return <p className="error">{error}</p>;
  if (!catalog) return <p className="muted">Loading OSS integration map…</p>;

  return (
    <section className="card">
      <h3>3 · OSS integration map</h3>
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
        Download compile artifacts for KiCad, tscircuit/circuit-json tools, fab, or agent pipelines.
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
