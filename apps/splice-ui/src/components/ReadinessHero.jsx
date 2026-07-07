import { buildReadinessSummary } from "../utils/readinessSummary.js";
import { StatusPill } from "./ProjectPanels.jsx";

export default function ReadinessHero({ pkg, benchSession, onGoDesign, onGoBench, onGoGates }) {
  const summary = buildReadinessSummary(pkg, benchSession);
  const hold = !summary.powerOk;

  return (
    <section className={`readiness-hero ${hold ? "readiness-hold" : "readiness-ok"}`}>
      <div className="readiness-hero-main">
        <p className="eyebrow">Readiness verdict</p>
        <div className="readiness-hero-head">
          <h2>{summary.headline}</h2>
          <StatusPill ok={summary.powerOk} label={summary.verdict} />
        </div>
        <p className="muted">{summary.subline}</p>
        {summary.issues.length > 0 && (
          <ul className="readiness-issues">
            {summary.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="readiness-hero-actions">
        {onGoDesign && (
          <button type="button" className="secondary small" onClick={onGoDesign}>
            Design verify →
          </button>
        )}
        {hold && summary.openCount > 0 && onGoBench && (
          <button type="button" className="primary small" onClick={onGoBench}>
            Close {summary.openCount} gate{summary.openCount === 1 ? "" : "s"} →
          </button>
        )}
        {onGoGates && (
          <button type="button" className="ghost small" onClick={onGoGates}>
            Safety gates
          </button>
        )}
      </div>
    </section>
  );
}
