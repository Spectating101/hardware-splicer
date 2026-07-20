import { useMemo, useState } from "react";

import { PERSISTENCE_STATUS, projectSnapshot } from "../projectSession/projectSession.js";
import {
  editMachineProject,
  stageMachineProjectReview,
} from "../projectSession/machineAuthoringApi.js";
import "./MachineAuthoringPanel.css";

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((row) => row.trim())
    .filter(Boolean);
}

export default function MachineAuthoringPanel({ session, onToast }) {
  const [mode, setMode] = useState("requirement");
  const [requirementId, setRequirementId] = useState("");
  const [statement, setStatement] = useState("");
  const [kind, setKind] = useState("functional");
  const [allocatedTo, setAllocatedTo] = useState("");
  const [interfaceId, setInterfaceId] = useState(session.machineProject?.interfaces?.[0]?.interface_id || "");
  const [contractType, setContractType] = useState("electrical");
  const [contractValues, setContractValues] = useState("{}");
  const [unresolvedFields, setUnresolvedFields] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastReview, setLastReview] = useState(null);

  const persisted =
    session.snapshotRevision > 0 &&
    [PERSISTENCE_STATUS.saved, PERSISTENCE_STATUS.restored].includes(session.persistenceStatus);
  const interfaces = session.machineProject?.interfaces || [];
  const objectIds = useMemo(
    () => [
      ...(session.machineProject?.subsystems || []).map((row) => row.subsystem_id),
      ...(session.machineProject?.components || []).map((row) => row.component_id),
    ],
    [session.machineProject],
  );

  if (!session.machineProject) return null;

  const submit = async () => {
    if (!persisted) {
      setError("Wait for the current project revision to finish saving before staging an edit.");
      return;
    }
    let operation;
    try {
      if (mode === "requirement") {
        if (!requirementId.trim() || !statement.trim()) {
          throw new Error("Requirement ID and statement are required.");
        }
        operation = {
          type: "upsert_requirement",
          payload: {
            requirement_id: requirementId.trim(),
            statement: statement.trim(),
            kind,
            allocated_to: splitList(allocatedTo),
            authority: "declared",
          },
        };
      } else {
        if (!interfaceId) throw new Error("Select an interface first.");
        let values;
        try {
          values = JSON.parse(contractValues || "{}");
        } catch {
          throw new Error("Contract values must be valid JSON.");
        }
        operation = {
          type: "update_interface_contract",
          payload: {
            interface_id: interfaceId,
            contract_type: contractType.trim() || "electrical",
            values,
            unresolved_fields: splitList(unresolvedFields),
            authority: "declared",
          },
        };
      }

      setBusy(true);
      setError("");
      const edited = await editMachineProject(session.machineProject, [operation]);
      const candidateSnapshot = {
        ...projectSnapshot(session),
        machineProject: edited.project,
      };
      const staged = await stageMachineProjectReview(session.projectId, candidateSnapshot, {
        baseRevision: session.snapshotRevision,
        note:
          note.trim() ||
          (mode === "requirement"
            ? `Edit requirement ${requirementId.trim()}`
            : `Edit ${interfaceId}/${contractType.trim() || "electrical"} contract`),
      });
      setLastReview(staged.review || null);
      window.dispatchEvent(new Event("hardware-splicer:review-created"));
      onToast?.(`Candidate staged as ${staged.review?.review_id}. Review it before acceptance.`);
    } catch (err) {
      setError(err.message);
      onToast?.(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card machine-authoring" data-testid="machine-authoring-panel">
      <div className="machine-authoring__header">
        <div>
          <p className="eyebrow">Machine authoring</p>
          <h2>Edit intent and interface contracts</h2>
          <p className="small muted">
            Edits produce a validated candidate and enter the review queue. This editor can declare design intent,
            but it cannot assign measured, verified, or authorized authority.
          </p>
        </div>
        <span className={`machine-authoring__state ${persisted ? "ready" : "waiting"}`}>
          {persisted ? `Based on revision ${session.snapshotRevision}` : "Waiting for saved revision"}
        </span>
      </div>

      <div className="machine-authoring__tabs">
        <button type="button" className={mode === "requirement" ? "active" : ""} onClick={() => setMode("requirement")}>
          Requirement
        </button>
        <button type="button" className={mode === "contract" ? "active" : ""} onClick={() => setMode("contract")}>
          Interface contract
        </button>
      </div>

      {mode === "requirement" ? (
        <div className="machine-authoring__form">
          <label>
            Requirement ID
            <input value={requirementId} onChange={(event) => setRequirementId(event.target.value)} placeholder="req-runtime" />
          </label>
          <label className="wide">
            Statement
            <textarea value={statement} onChange={(event) => setStatement(event.target.value)} rows={2} placeholder="The machine shall..." />
          </label>
          <label>
            Kind
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="functional">Functional</option>
              <option value="performance">Performance</option>
              <option value="safety">Safety</option>
              <option value="interface">Interface</option>
              <option value="constraint">Constraint</option>
            </select>
          </label>
          <label>
            Allocate to
            <input value={allocatedTo} onChange={(event) => setAllocatedTo(event.target.value)} placeholder={objectIds.slice(0, 3).join(", ")} />
          </label>
        </div>
      ) : (
        <div className="machine-authoring__form">
          <label>
            Interface
            <select value={interfaceId} onChange={(event) => setInterfaceId(event.target.value)} disabled={!interfaces.length}>
              {!interfaces.length && <option value="">No interfaces defined</option>}
              {interfaces.map((row) => <option key={row.interface_id} value={row.interface_id}>{row.name}</option>)}
            </select>
          </label>
          <label>
            Contract type
            <input value={contractType} onChange={(event) => setContractType(event.target.value)} />
          </label>
          <label className="wide">
            Values (JSON)
            <textarea value={contractValues} onChange={(event) => setContractValues(event.target.value)} rows={3} />
          </label>
          <label className="wide">
            Unresolved fields
            <input value={unresolvedFields} onChange={(event) => setUnresolvedFields(event.target.value)} placeholder="pin_mapping, voltage_domain" />
          </label>
        </div>
      )}

      <label className="machine-authoring__note">
        Proposal note
        <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why this change is needed" />
      </label>

      {error && <p className="machine-authoring__error" role="alert">{error}</p>}
      {lastReview && (
        <p className="small muted" data-testid="machine-authoring-staged">
          Staged {lastReview.review_id} against revision {lastReview.base_revision}. No project revision has changed yet.
        </p>
      )}

      <div className="machine-authoring__actions">
        <button type="button" className="primary" onClick={submit} disabled={busy || !persisted}>
          Stage candidate for review
        </button>
      </div>
    </section>
  );
}
