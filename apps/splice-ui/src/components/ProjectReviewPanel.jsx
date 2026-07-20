import { useCallback, useEffect, useMemo, useState } from "react";

import {
  decideProjectReview,
  listProjectReviews,
  listProjectRevisions,
  loadProjectReview,
} from "../projectSession/projectReviewApi.js";
import "./ProjectReviewPanel.css";

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function collectFlags(review) {
  if (!review?.diff) return [];
  const direct = review.diff.review_flags || [];
  const objectFlags = (review.diff.object_changes || []).flatMap((change) =>
    (change.review_flags || []).map((flag) => ({ ...flag, collection: change.collection })),
  );
  return [...direct, ...objectFlags];
}

export default function ProjectReviewPanel({ projectId, currentRevision, onToast }) {
  const [reviews, setReviews] = useState([]);
  const [revisions, setRevisions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selected, setSelected] = useState(null);
  const [actor, setActor] = useState("owner");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!projectId) return;
    try {
      const [reviewBody, revisionBody] = await Promise.all([
        listProjectReviews(projectId),
        listProjectRevisions(projectId),
      ]);
      const nextReviews = reviewBody.reviews || [];
      setReviews(nextReviews);
      setRevisions(revisionBody.revisions || []);
      setError("");
      setSelectedId((prior) => {
        if (prior && nextReviews.some((row) => row.review_id === prior)) return prior;
        return nextReviews.find((row) => row.status === "pending")?.review_id || nextReviews[0]?.review_id || null;
      });
    } catch (err) {
      setError(err.message);
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh, currentRevision]);

  useEffect(() => {
    if (!projectId || !selectedId) {
      setSelected(null);
      return;
    }
    let cancelled = false;
    loadProjectReview(projectId, selectedId)
      .then((body) => {
        if (!cancelled) setSelected(body.review || null);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, selectedId]);

  const pendingCount = reviews.filter((row) => row.status === "pending").length;
  const flags = useMemo(() => collectFlags(selected), [selected]);
  const requiredFlags = flags.filter((flag) => flag.severity === "required");

  const decide = async (decision) => {
    if (!selected?.review_id || !actor.trim()) return;
    setBusy(true);
    try {
      const body = await decideProjectReview(projectId, selected.review_id, {
        decision,
        actor: actor.trim(),
        note: note.trim(),
      });
      const review = body.review;
      setSelected(review);
      setNote("");
      await refresh();
      const acceptedRevision = review?.decision?.accepted_revision;
      onToast?.(
        decision === "accepted"
          ? `Review accepted as revision ${acceptedRevision}. Reopen the project to load it.`
          : "Review rejected; no project revision was created.",
      );
    } catch (err) {
      setError(err.message);
      onToast?.(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!projectId || !currentRevision) return null;

  return (
    <section className="card project-review" data-testid="project-review-panel">
      <div className="project-review__header">
        <div>
          <p className="eyebrow">Revision control</p>
          <h2>Engineering review queue</h2>
          <p className="small muted">
            Candidates remain outside project history until accepted. Acceptance controls persistence only;
            it does not grant engineering authority.
          </p>
        </div>
        <div className="project-review__metrics" aria-label="Review metrics">
          <span><strong>{pendingCount}</strong> pending</span>
          <span><strong>{currentRevision}</strong> current revision</span>
        </div>
      </div>

      {error && <p className="project-review__error" role="alert">{error}</p>}

      <div className="project-review__layout">
        <div className="project-review__queue">
          <h3>Proposals</h3>
          {reviews.length === 0 ? (
            <p className="small muted">No staged proposals. Agent and API clients can submit candidates for review.</p>
          ) : (
            reviews.map((review) => (
              <button
                type="button"
                key={review.review_id}
                className={`project-review__item ${selectedId === review.review_id ? "active" : ""}`}
                onClick={() => setSelectedId(review.review_id)}
              >
                <span>
                  <strong>{review.note || review.review_id}</strong>
                  <small>Base r{review.base_revision} · {review.created_by}</small>
                </span>
                <span className={`project-review__status project-review__status--${review.status}`}>
                  {review.status}
                </span>
              </button>
            ))
          )}
        </div>

        <div className="project-review__detail">
          {!selected ? (
            <p className="small muted">Select a proposal to inspect its semantic changes.</p>
          ) : (
            <>
              <div className="project-review__summary">
                <div>
                  <h3>{selected.note || selected.review_id}</h3>
                  <p className="small muted">
                    Proposed by {selected.created_by} · {formatTime(selected.created_at)} · base revision {selected.base_revision}
                  </p>
                </div>
                <span className={`project-review__status project-review__status--${selected.status}`}>
                  {selected.status}
                </span>
              </div>

              <div className="project-review__change-grid">
                <span><strong>{selected.summary?.added || 0}</strong> added</span>
                <span><strong>{selected.summary?.removed || 0}</strong> removed</span>
                <span><strong>{selected.summary?.modified || 0}</strong> modified</span>
                <span><strong>{requiredFlags.length}</strong> required reviews</span>
              </div>

              {flags.length > 0 ? (
                <div className="project-review__flags" data-testid="project-review-flags">
                  {flags.map((flag, index) => (
                    <div key={`${flag.code}-${flag.object_id || index}`} className={`project-review__flag project-review__flag--${flag.severity}`}>
                      <strong>{flag.code.replaceAll("_", " ")}</strong>
                      <span>{flag.message}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="small muted">No authority or safety review flags were raised.</p>
              )}

              {(selected.diff?.object_changes || []).length > 0 && (
                <details className="project-review__changes">
                  <summary>Changed engineering objects</summary>
                  {(selected.diff.object_changes || []).map((change) => (
                    <div key={`${change.collection}-${change.object_id}`}>
                      <strong>{change.change_type}: {change.collection}/{change.object_id}</strong>
                      <span>{change.field_changes?.length || 0} field changes</span>
                    </div>
                  ))}
                </details>
              )}

              {selected.status === "pending" ? (
                <div className="project-review__decision">
                  <label>
                    Reviewer
                    <input value={actor} onChange={(event) => setActor(event.target.value)} />
                  </label>
                  <label>
                    Decision note
                    <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} />
                  </label>
                  <div className="project-review__actions">
                    <button type="button" className="secondary" disabled={busy || !actor.trim()} onClick={() => decide("rejected")}>
                      Reject candidate
                    </button>
                    <button type="button" className="primary" disabled={busy || !actor.trim()} onClick={() => decide("accepted")}>
                      Accept as next revision
                    </button>
                  </div>
                </div>
              ) : (
                <p className="small muted">
                  Decided by {selected.decision?.actor || "—"} · {formatTime(selected.decision?.decided_at)}
                  {selected.decision?.accepted_revision ? ` · revision ${selected.decision.accepted_revision}` : ""}
                </p>
              )}
            </>
          )}
        </div>

        <div className="project-review__history">
          <h3>Revision provenance</h3>
          {revisions.slice(0, 8).map((revision) => (
            <div key={revision.revision} className="project-review__revision">
              <span><strong>r{revision.revision}</strong> · {revision.current_stage}</span>
              <small>{revision.review_id ? `Reviewed by ${revision.review_actor || "unknown"}` : "Direct workspace save"}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
