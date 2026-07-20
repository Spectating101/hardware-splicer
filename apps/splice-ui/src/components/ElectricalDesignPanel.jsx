import { useEffect, useMemo, useState } from "react";

import { PERSISTENCE_STATUS, projectSnapshot } from "../projectSession/projectSession.js";
import { stageMachineProjectReview } from "../projectSession/machineAuthoringApi.js";
import {
  checkElectricalDesign,
  editElectricalDesign,
  projectElectricalDesign,
} from "../projectSession/electricalDesignApi.js";
import "./ElectricalDesignPanel.css";

function numberOrNull(value) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const parsed = Number(text);
  if (!Number.isFinite(parsed)) throw new Error(`Expected a number, received ${value}`);
  return parsed;
}

export default function ElectricalDesignPanel({ session, onToast }) {
  const [design, setDesign] = useState(null);
  const [erc, setErc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastReview, setLastReview] = useState(null);
  const [mode, setMode] = useState("net");
  const [netId, setNetId] = useState("");
  const [netName, setNetName] = useState("");
  const [netKind, setNetKind] = useState("signal");
  const [voltageMin, setVoltageMin] = useState("");
  const [voltageMax, setVoltageMax] = useState("");
  const [peakCurrent, setPeakCurrent] = useState("");
  const [pinId, setPinId] = useState("");
  const [targetNetId, setTargetNetId] = useState("");
  const [note, setNote] = useState("");

  const persisted =
    session.snapshotRevision > 0 &&
    [PERSISTENCE_STATUS.saved, PERSISTENCE_STATUS.restored].includes(session.persistenceStatus);
  const storedDesign = session.machineProject?.discipline_payloads?.electrical_design || null;

  useEffect(() => {
    if (!session.machineProject) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    const request = storedDesign
      ? checkElectricalDesign(storedDesign)
      : projectElectricalDesign(session.machineProject);
    request
      .then((body) => {
        if (cancelled) return;
        setDesign(body.design || null);
        setErc(body.erc || null);
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
  }, [session.machineProject, storedDesign]);

  const unconnectedPins = useMemo(
    () => (design?.pins || []).filter((row) => !row.net_id),
    [design],
  );

  if (!session.machineProject) return null;

  const stageEdit = async () => {
    if (!persisted || !design) {
      setError("Wait for a saved project revision and electrical projection before editing.");
      return;
    }
    let operation;
    try {
      if (mode === "net") {
        if (!netId.trim() || !netName.trim()) throw new Error("Net ID and name are required.");
        operation = {
          type: "upsert_net",
          payload: {
            net_id: netId.trim(),
            name: netName.trim(),
            kind: netKind,
            voltage_min_v: numberOrNull(voltageMin),
            voltage_max_v: numberOrNull(voltageMax),
            peak_current_a: numberOrNull(peakCurrent),
            authority: "declared",
          },
        };
      } else {
        if (!pinId || !targetNetId) throw new Error("Pin and target net are required.");
        operation = {
          type: "connect_pin",
          payload: { pin_id: pinId, net_id: targetNetId },
        };
      }

      setBusy(true);
      setError("");
      const edited = await editElectricalDesign(design, [operation]);
      const candidateMachine = {
        ...session.machineProject,
        discipline_payloads: {
          ...(session.machineProject.discipline_payloads || {}),
          electrical_design: edited.design,
        },
      };
      const candidateSnapshot = {
        ...projectSnapshot(session),
        machineProject: candidateMachine,
      };
      const staged = await stageMachineProjectReview(session.projectId, candidateSnapshot, {
        baseRevision: session.snapshotRevision,
        createdBy: "electrical-author",
        note:
          note.trim() ||
          (mode === "net" ? `Create or update net ${netId.trim()}` : `Connect ${pinId} to ${targetNetId}`),
        includeMetadata: true,
      });
      setLastReview(staged.review || null);
      window.dispatchEvent(new Event("hardware-splicer:review-created"));
      onToast?.(`Electrical candidate staged as ${staged.review?.review_id}. Review before acceptance.`);
    } catch (err) {
      setError(err.message);
      onToast?.(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card electrical-design" data-testid="electrical-design-panel">
      <div className="electrical-design__header">
        <div>
          <p className="eyebrow">Electrical authoring</p>
          <h2>Pins, nets, power domains, and ERC</h2>
          <p className="small muted">
            The canvas is not electrical truth. This workspace represents exact pin ownership and net membership,
            then runs rule checks before a candidate can enter project history.
          </p>
        </div>
        <span className={`electrical-design__state ${persisted ? "ready" : "waiting"}`}>
          {loading ? "Projecting electrical design" : persisted ? `Based on revision ${session.snapshotRevision}` : "Waiting for saved revision"}
        </span>
      </div>

      {error && <p className="electrical-design__error" role="alert">{error}</p>}

      {design && (
        <>
          <div className="electrical-design__metrics">
            <span><strong>{design.components?.length || 0}</strong> components</span>
            <span><strong>{design.pins?.length || 0}</strong> pins</span>
            <span><strong>{design.nets?.length || 0}</strong> nets</span>
            <span><strong>{erc?.error_count || 0}</strong> ERC errors</span>
            <span><strong>{erc?.warning_count || 0}</strong> warnings</span>
          </div>

          <div className="electrical-design__layout">
            <div>
              <h3>Nets</h3>
              <div className="electrical-design__list">
                {(design.nets || []).map((net) => (
                  <div key={net.net_id}>
                    <strong>{net.name}</strong>
                    <span>{net.kind} · {net.pin_ids?.length || 0} pins · {net.authority}</span>
                    {net.unresolved_fields?.length > 0 && <small>{net.unresolved_fields.join(", ")}</small>}
                  </div>
                ))}
                {!design.nets?.length && <p className="small muted">No nets yet.</p>}
              </div>
            </div>
            <div>
              <h3>ERC</h3>
              <div className="electrical-design__issues">
                {(erc?.issues || []).map((issue, index) => (
                  <div key={`${issue.code}-${issue.object_id || index}`} className={`electrical-design__issue electrical-design__issue--${issue.severity}`}>
                    <strong>{issue.code.replaceAll("_", " ")}</strong>
                    <span>{issue.message}</span>
                  </div>
                ))}
                {!erc?.issues?.length && <p className="small muted">No electrical rule violations detected.</p>}
              </div>
            </div>
          </div>

          <div className="electrical-design__tabs">
            <button type="button" className={mode === "net" ? "active" : ""} onClick={() => setMode("net")}>Create net</button>
            <button type="button" className={mode === "connect" ? "active" : ""} onClick={() => setMode("connect")}>Connect pin</button>
          </div>

          {mode === "net" ? (
            <div className="electrical-design__form">
              <label>Net ID<input value={netId} onChange={(event) => setNetId(event.target.value)} placeholder="vcc-3v3" /></label>
              <label>Name<input value={netName} onChange={(event) => setNetName(event.target.value)} placeholder="VCC_3V3" /></label>
              <label>Kind<select value={netKind} onChange={(event) => setNetKind(event.target.value)}><option value="signal">Signal</option><option value="power">Power</option><option value="ground">Ground</option><option value="analog">Analog</option><option value="differential">Differential</option></select></label>
              <label>Voltage min<input value={voltageMin} onChange={(event) => setVoltageMin(event.target.value)} inputMode="decimal" /></label>
              <label>Voltage max<input value={voltageMax} onChange={(event) => setVoltageMax(event.target.value)} inputMode="decimal" /></label>
              <label>Peak current A<input value={peakCurrent} onChange={(event) => setPeakCurrent(event.target.value)} inputMode="decimal" /></label>
            </div>
          ) : (
            <div className="electrical-design__form">
              <label>
                Unconnected pin
                <select value={pinId} onChange={(event) => setPinId(event.target.value)}>
                  <option value="">Select pin</option>
                  {unconnectedPins.map((pin) => <option key={pin.pin_id} value={pin.pin_id}>{pin.component_id}/{pin.name} ({pin.number})</option>)}
                </select>
              </label>
              <label>
                Target net
                <select value={targetNetId} onChange={(event) => setTargetNetId(event.target.value)}>
                  <option value="">Select net</option>
                  {(design.nets || []).map((net) => <option key={net.net_id} value={net.net_id}>{net.name}</option>)}
                </select>
              </label>
            </div>
          )}

          <label className="electrical-design__note">Proposal note<input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Why this electrical change is needed" /></label>

          {lastReview && (
            <p className="small muted" data-testid="electrical-design-staged">
              Staged {lastReview.review_id} against revision {lastReview.base_revision}. Electrical design has not changed yet.
            </p>
          )}

          <div className="electrical-design__actions">
            <button type="button" className="primary" disabled={busy || loading || !persisted} onClick={stageEdit}>
              Run ERC and stage candidate
            </button>
          </div>
        </>
      )}
    </section>
  );
}
