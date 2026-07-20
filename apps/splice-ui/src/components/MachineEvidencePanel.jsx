import { useMemo, useState } from "react";

import { PERSISTENCE_STATUS, projectSnapshot } from "../projectSession/projectSession.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";
import { recordMachineEvidence } from "../projectSession/machineEvidenceApi.js";
import BenchCaptureImportPanel from "./BenchCaptureImportPanel.jsx";
import "./MachineEvidencePanel.css";

function targetRows(project) {
  const definitions = [
    ["requirements", "requirement_id", "statement"],
    ["subsystems", "subsystem_id", "name"],
    ["components", "component_id", "name"],
    ["interfaces", "interface_id", "name"],
    ["constraints", "constraint_id", "name"],
    ["artifacts", "artifact_id", "kind"],
  ];
  return definitions.flatMap(([collection, idField, labelField]) =>
    (project?.[collection] || []).map((row) => ({
      collection,
      objectId: row[idField],
      label: `${row[labelField] || row[idField]} · ${collection.slice(0, -1)}`,
      authority: row.authority || "unknown",
    })),
  );
}

export default function MachineEvidencePanel({ session, onToast }) {
  const targets = useMemo(() => targetRows(session.machineProject), [session.machineProject]);
  const [targetKey, setTargetKey] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [kind, setKind] = useState("bench_test");
  const [basis, setBasis] = useState("instrument");
  const [reference, setReference] = useState("");
  const [simulated, setSimulated] = useState(false);
  const [evidenceAuthority, setEvidenceAuthority] = useState("measured");
  const [promotionAuthority, setPromotionAuthority] = useState("measured");
  const [verificationId, setVerificationId] = useState("");
  const [verificationName, setVerificationName] = useState("");
  const [verificationType, setVerificationType] = useState("test");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastReview, setLastReview] = useState(null);

  const persisted =
    session.snapshotRevision > 0 &&
    [PERSISTENCE_STATUS.saved, PERSISTENCE_STATUS.restored].includes(session.persistenceStatus);
  const selected = targets.find((row) => `${row.collection}|${row.objectId}` === targetKey) || null;
  const needsVerification = ["verified", "authorized"].includes(promotionAuthority);

  if (!session.machineProject) return null;

  const submit = async () => {
    if (!persisted) {
      setError("Wait for the current revision to finish saving before recording evidence.");
      return;
    }
    if (!selected || !evidenceId.trim() || !kind.trim() || !basis.trim()) {
      setError("Target, evidence ID, kind, and basis are required.");
      return;
    }
    if (needsVerification && (!verificationId.trim() || !verificationName.trim())) {
      setError("Verified and authorized promotions require a verification ID and name.");
      return;
    }

    const evidence = {
      evidence_id: evidenceId.trim(),
      kind: kind.trim(),
      basis: basis.trim(),
      ref: reference.trim() || null,
      supports: [selected.objectId],
      authority: evidenceAuthority,
      simulated,
    };
    const verification = needsVerification
      ? {
          verification_id: verificationId.trim(),
          name: verificationName.trim(),
          method_type: verificationType,
          status: "passed",
          requirement_ids: selected.collection === "requirements" ? [selected.objectId] : [],
          target_ids: selected.collection === "requirements" ? [] : [selected.objectId],
          evidence_ids: [evidence.evidence_id],
          authority: "verified",
        }
      : null;

    try {
      setBusy(true);
      setError("");
      const candidate = await recordMachineEvidence(session.machineProject, {
        evidence,
        verification,
        promotions: [
          {
            collection: selected.collection,
            object_id: selected.objectId,
            authority: promotionAuthority,
          },
        ],
      });
      const candidateSnapshot = {
        ...projectSnapshot(session),
        machineProject: candidate.project,
      };
      const staged = await stageMachineProjectReview(session.projectId, candidateSnapshot, {
        baseRevision: session.snapshotRevision,
        createdBy: "evidence-recorder",
        note:
          note.trim() ||
          `Record ${evidence.evidence_id} and promote ${selected.collection}/${selected.objectId} to ${promotionAuthority}`,
      });
      setLastReview(staged.review || null);
      window.dispatchEvent(new Event("hardware-splicer:review-created"));
      onToast?.(`Evidence candidate staged as ${staged.review?.review_id}. Review before acceptance.`);
    } catch (err) {
      setError(err.message);
      onToast?.(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="card machine-evidence" data-testid="machine-evidence-panel">
        <div className="machine-evidence__header">
          <div>
            <p className="eyebrow">Evidence authority</p>
            <h2>Record evidence and propose authority</h2>
            <p className="small muted">
              Evidence, passing verification, and the authority transition are recorded in one candidate. Simulated
              evidence cannot promote physical targets.
            </p>
          </div>
          <span className={`machine-evidence__state ${persisted ? "ready" : "waiting"}`}>
            {persisted ? `Based on revision ${session.snapshotRevision}` : "Waiting for saved revision"}
          </span>
        </div>

        <div className="machine-evidence__form">
          <label className="wide">
            Promotion target
            <select value={targetKey} onChange={(event) => setTargetKey(event.target.value)}>
              <option value="">Select engineering object</option>
              {targets.map((row) => (
                <option key={`${row.collection}-${row.objectId}`} value={`${row.collection}|${row.objectId}`}>
                  {row.label} · current {row.authority}
                </option>
              ))}
            </select>
          </label>
          <label>
            Evidence ID
            <input value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} placeholder="evidence-power-load" />
          </label>
          <label>
            Evidence kind
            <input value={kind} onChange={(event) => setKind(event.target.value)} placeholder="bench_test" />
          </label>
          <label>
            Basis
            <input value={basis} onChange={(event) => setBasis(event.target.value)} placeholder="instrument" />
          </label>
          <label>
            Artifact or capture reference
            <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="captures/power-load.json" />
          </label>
          <label>
            Evidence authority
            <select value={evidenceAuthority} onChange={(event) => setEvidenceAuthority(event.target.value)}>
              <option value="observed">Observed</option>
              <option value="measured">Measured</option>
              <option value="verified">Verified</option>
              <option value="authorized">Authorized</option>
            </select>
          </label>
          <label>
            Proposed target authority
            <select value={promotionAuthority} onChange={(event) => setPromotionAuthority(event.target.value)}>
              <option value="observed">Observed</option>
              <option value="measured">Measured</option>
              <option value="verified">Verified</option>
              <option value="authorized">Authorized</option>
            </select>
          </label>
          <label className="machine-evidence__check">
            <input type="checkbox" checked={simulated} onChange={(event) => setSimulated(event.target.checked)} />
            Simulated evidence
          </label>
        </div>

        {needsVerification && (
          <div className="machine-evidence__verification">
            <h3>Passing verification</h3>
            <div className="machine-evidence__form">
              <label>
                Verification ID
                <input value={verificationId} onChange={(event) => setVerificationId(event.target.value)} placeholder="verify-power-load" />
              </label>
              <label>
                Verification name
                <input value={verificationName} onChange={(event) => setVerificationName(event.target.value)} placeholder="Power load test" />
              </label>
              <label>
                Method
                <select value={verificationType} onChange={(event) => setVerificationType(event.target.value)}>
                  <option value="analysis">Analysis</option>
                  <option value="inspection">Inspection</option>
                  <option value="test">Test</option>
                  <option value="demonstration">Demonstration</option>
                </select>
              </label>
            </div>
          </div>
        )}

        <label className="machine-evidence__note">
          Proposal note
          <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="What was measured and why it supports this claim" />
        </label>

        {error && <p className="machine-evidence__error" role="alert">{error}</p>}
        {lastReview && (
          <p className="small muted" data-testid="machine-evidence-staged">
            Staged {lastReview.review_id} against revision {lastReview.base_revision}. Authority has not changed yet.
          </p>
        )}

        <div className="machine-evidence__actions">
          <button type="button" className="primary" disabled={busy || !persisted} onClick={submit}>
            Stage evidence candidate
          </button>
        </div>
      </section>

      <BenchCaptureImportPanel session={session} onToast={onToast} />
    </>
  );
}
