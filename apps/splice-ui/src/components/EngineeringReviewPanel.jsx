import { useCallback, useEffect, useMemo, useState } from "react";

import { downloadBuildArtifact } from "../api.js";
import {
  fetchEngineeringReviewStatus,
  runEngineeringReview,
} from "../engineeringReviewApi.js";
import "./EngineeringReviewPanel.css";

const STATUS_LABELS = {
  blocked: "Blocked",
  review_required: "Review required",
  partial: "Partial review",
  failed: "Review failed",
  clear: "No external blockers",
};

const SEVERITY_ORDER = {
  blocker: 0,
  warning: 1,
  advisory: 2,
  info: 3,
};

function formatCoverage(value) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(Number(value))}%`;
}

function FindingCard({ finding }) {
  const references = [
    ...(finding.components || []).map((value) => `component ${value}`),
    ...(finding.nets || []).map((value) => `net ${value}`),
  ];

  return (
    <article className={`engineering-review__finding engineering-review__finding--${finding.severity || "info"}`}>
      <div className="engineering-review__finding-head">
        <span className={`engineering-review__severity engineering-review__severity--${finding.severity || "info"}`}>
          {finding.severity || "info"}
        </span>
        <span className="mono small">{finding.rule_id}</span>
      </div>
      <strong>{finding.title}</strong>
      {finding.recommendation && <p>{finding.recommendation}</p>}
      <p className="small muted">
        {finding.analyzer_type} · {finding.confidence || "confidence unspecified"}
        {references.length ? ` · ${references.join(" · ")}` : ""}
      </p>
    </article>
  );
}

export default function EngineeringReviewPanel({ buildDir }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    if (!buildDir) return;
    setError("");
    try {
      setStatus(await fetchEngineeringReviewStatus(buildDir));
    } catch (err) {
      setError(err.message);
    }
  }, [buildDir]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const review = status?.latest_review || null;
  const summary = review?.summary || null;
  const adapter = status?.adapter || {};
  const findings = useMemo(
    () =>
      [...(review?.findings || [])]
        .sort(
          (left, right) =>
            (SEVERITY_ORDER[left.severity] ?? 9) - (SEVERITY_ORDER[right.severity] ?? 9),
        )
        .slice(0, 16),
    [review],
  );

  const runReview = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await runEngineeringReview(buildDir, {
        force: Boolean(review),
      });
      if (result.skipped) {
        setMessage(result.reason || "Engineering review adapter is unavailable.");
      } else {
        setStatus((prior) => ({ ...(prior || {}), latest_review: result }));
        setMessage(result.cached ? "Existing review is already current." : "Engineering review saved to the project package.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadReview = async () => {
    setError("");
    try {
      await downloadBuildArtifact(buildDir, "build_compilation/ENGINEERING_REVIEW.json");
    } catch (err) {
      setError(err.message);
    }
  };

  if (!buildDir) return null;
  if (!status && !error) {
    return (
      <section className="card engineering-review" data-testid="engineering-review-panel">
        <p className="muted">Loading engineering review capability…</p>
      </section>
    );
  }

  return (
    <section className="card engineering-review" data-testid="engineering-review-panel">
      <div className="engineering-review__header">
        <div>
          <p className="eyebrow">External evidence</p>
          <h3>Engineering review</h3>
          <p className="muted">
            Run deterministic schematic, PCB, and Gerber analysis. Results become observed evidence;
            they may block release policy but never authorize fabrication.
          </p>
        </div>
        <span className={`engineering-review__adapter ${adapter.available ? "available" : "missing"}`}>
          {adapter.available ? "Analyzer ready" : "Analyzer not configured"}
        </span>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="muted small">{message}</p>}

      <div className="engineering-review__toolchain">
        <div>
          <strong>{adapter.name || "kicad-happy"}</strong>
          <p className="small muted">
            Read-only · MIT · authority ceiling: {adapter.authority_ceiling || "observed"}
          </p>
        </div>
        <div className="engineering-review__chips">
          {(status?.supported_inputs || status?.inputs?.map((row) => row.analyzer_type) || []).map((item) => (
            <span key={item} className="chip small">{item}</span>
          ))}
        </div>
      </div>

      {!adapter.available && (
        <div className="engineering-review__setup">
          <strong>Connect the review engine</strong>
          <p className="small muted">{adapter.setup?.instruction}</p>
          <code>export HARDWARE_SPLICER_KICAD_HAPPY_ROOT=/path/to/kicad-happy</code>
        </div>
      )}

      {summary ? (
        <>
          <div className={`engineering-review__summary engineering-review__summary--${summary.status || "clear"}`}>
            <div>
              <span className="eyebrow">{STATUS_LABELS[summary.status] || summary.status}</span>
              <strong>{summary.headline}</strong>
            </div>
            <span className="chip small">Observed evidence only</span>
          </div>

          <div className="engineering-review__metrics" aria-label="Engineering review metrics">
            <span><strong>{summary.blocker_count || 0}</strong> blockers</span>
            <span><strong>{summary.warning_count || 0}</strong> warnings</span>
            <span><strong>{summary.analysis_count || 0}</strong> analyzers</span>
            <span><strong>{formatCoverage(summary.provenance_coverage_pct)}</strong> provenance</span>
          </div>

          {findings.length > 0 ? (
            <div className="engineering-review__findings">
              {findings.map((finding) => (
                <FindingCard key={finding.finding_id} finding={finding} />
              ))}
            </div>
          ) : (
            <p className="small muted">No normalized findings were reported by the completed analyzers.</p>
          )}

          {(review.failures || []).length > 0 && (
            <details className="engineering-review__failures">
              <summary>{review.failures.length} analyzer failure(s)</summary>
              {(review.failures || []).map((failure, index) => (
                <p key={`${failure.analyzer_type}-${failure.reason}-${index}`} className="small">
                  <strong>{failure.analyzer_type}</strong>: {failure.reason} — {failure.detail}
                </p>
              ))}
            </details>
          )}
        </>
      ) : (
        <p className="small muted">
          No external review has been recorded for this build. KiCad compile truth remains available above.
        </p>
      )}

      <div className="engineering-review__actions">
        <button
          type="button"
          className="primary small"
          disabled={busy || !status?.can_run}
          onClick={runReview}
        >
          {busy ? "Reviewing…" : review ? "Run review again" : "Run engineering review"}
        </button>
        {review && (
          <button type="button" className="secondary small" onClick={downloadReview}>
            Download review JSON
          </button>
        )}
        <button type="button" className="ghost small" disabled={busy} onClick={refresh}>
          Refresh adapters
        </button>
      </div>
    </section>
  );
}
