const STAGES = [
  { id: "queued", label: "Queued" },
  { id: "running", label: "Compiling KiCad carrier" },
  { id: "succeeded", label: "Complete" },
];

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function BuildOverlay({ active, status, stageLabel, elapsedSec, error, projectName }) {
  if (!active && !error) return null;

  const stageIndex = status === "succeeded" ? 2 : status === "running" ? 1 : 0;

  return (
    <div className="build-overlay" role="dialog" aria-modal="true" aria-label="Building project">
      <div className="build-overlay-card">
        {error ? (
          <>
            <div className="build-overlay-icon error">!</div>
            <h2>Build failed</h2>
            <p className="error">{error}</p>
          </>
        ) : (
          <>
            <div className="build-overlay-spinner" aria-hidden />
            <h2>{projectName ? `Building ${projectName}` : "Building your project"}</h2>
            <p className="build-overlay-stage">{stageLabel || "Working…"}</p>
            <p className="muted small">Typical compile time: 30–90 seconds · {formatElapsed(elapsedSec)} · fails after ~3 min if stuck</p>
            <ol className="build-stage-list">
              {STAGES.map((stage, index) => (
                <li key={stage.id} className={index <= stageIndex ? "done" : index === stageIndex ? "active" : ""}>
                  <span className="build-stage-dot" />
                  {stage.label}
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}
