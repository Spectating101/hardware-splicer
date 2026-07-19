import { useMemo, useState } from "react";
import { deriveEvidenceTruth, evidenceTone } from "../projectSession/deriveEvidenceTruth.js";
import "./EvidenceWorkbenchPanel.css";

function titleCase(value) {
  return String(value || "unknown")
    .replace(/[_:.\-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function downloadJson(filename, value) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function Metric({ label, value, detail, tone = "neutral" }) {
  return (
    <div className={`evidence-metric evidence-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function BackendCard({ name, row }) {
  return (
    <div className={`backend-card backend-card--${row.state}`}>
      <div>
        <strong>{name}</strong>
        <span className="backend-card__state">{titleCase(row.state)}</span>
      </div>
      <p>{row.detail}</p>
    </div>
  );
}

function InterfaceListItem({ item, active, onSelect }) {
  const contract = item.interface_contract || {};
  const blockers = item.blockers || contract.unresolved_fields || [];
  const ready = item.compile_status === "ready" && contract.firmware_authorized === true;
  return (
    <button
      type="button"
      className={`evidence-interface-item ${active ? "active" : ""}`}
      onClick={onSelect}
      data-testid={`evidence-interface-${contract.interface_id || contract.block_id}`}
    >
      <span className={`authority-dot authority-dot--${ready ? "ok" : "blocked"}`} aria-hidden />
      <span>
        <strong>{contract.functional_role || contract.block_id || "Donor interface"}</strong>
        <small>{contract.virtual_module_id || contract.interface_id}</small>
      </span>
      <span className="evidence-interface-item__count">{blockers.length}</span>
    </button>
  );
}

function ContractEditor({ item, benchSession, onContractUpdate, onToast }) {
  const contract = item?.interface_contract || {};
  const firstContact = contract.contacts?.[0] || {};
  const firstSignal = contract.signals?.[0] || {};
  const gate = (benchSession?.open_gates || []).find(
    (row) => row?.requires_contract_edit && row?.interface_id === contract.interface_id,
  );
  const [draft, setDraft] = useState({
    signalId: firstSignal.signal_id || "enable",
    contactId: firstSignal.contact_id || firstContact.contact_id || "",
    connectorRef: firstContact.connector_ref || "",
    pinNumber: firstContact.pin_number || "",
    direction: firstSignal.direction || "input",
    voltageMax: firstSignal.voltage_max_v?.value ?? "3.3",
    activeLevel: firstSignal.active_level?.value || "high",
    controllerPin: firstSignal.controller_pin?.value || "",
    method: "DMM plus protected stimulus",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  if (item?.legacy_fallback) {
    return (
      <div className="evidence-callout evidence-callout--warn">
        <strong>Regenerate before editing</strong>
        <p>Legacy builds do not contain a canonical contract that can be safely updated.</p>
      </div>
    );
  }
  if (contract.firmware_authorized && !gate) {
    return (
      <div className="evidence-callout evidence-callout--ok">
        <strong>Interface structure verified</strong>
        <p>Control semantics and MCU binding are authoritative. Continue with physical measurement gates.</p>
      </div>
    );
  }
  if (!gate || !onContractUpdate) {
    return (
      <div className="evidence-callout evidence-callout--neutral">
        <strong>Open Bench to initialize contract gates</strong>
        <p>The editor activates after the build's Bench session has loaded its canonical interface gates.</p>
      </div>
    );
  }

  const update = (field, value) => setDraft((current) => ({ ...current, [field]: value }));
  const required = draft.signalId.trim() && draft.contactId.trim() && draft.controllerPin.trim() && draft.voltageMax !== "";

  const submit = async (event) => {
    event.preventDefault();
    if (!required || submitting) return;
    setSubmitting(true);
    setResult(null);
    try {
      const response = await onContractUpdate([
        {
          gate_id: gate.gate_id,
          status: "verified",
          contract_update: {
            operation: "upsert_signal",
            interface_id: contract.interface_id,
            signal_id: draft.signalId.trim(),
            contact_id: draft.contactId.trim(),
            connector_ref: draft.connectorRef.trim(),
            pin_number: draft.pinNumber.trim(),
            direction: draft.direction,
            voltage_max_v: Number(draft.voltageMax),
            active_level: draft.activeLevel.trim(),
            controller_pin: draft.controllerPin.trim(),
            evidence_id: `ui-contract:${contract.interface_id}:${Date.now()}`,
            method: draft.method.trim(),
            producer: "operator+instrument",
            notes: draft.notes.trim(),
          },
        },
      ]);
      const applied = response?.last_submission?.applied?.[0];
      if (!applied?.ok) throw new Error(applied?.reason || applied?.error || "Contract update rejected");
      setResult({ ok: true, message: "Interface contract persisted and authority recomputed." });
      onToast?.("Donor interface contract updated");
    } catch (error) {
      setResult({ ok: false, message: error.message });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="evidence-section evidence-contract-editor" data-testid="evidence-contract-editor">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Resolve interface structure</p>
          <h4>Bind one evidenced control signal</h4>
        </div>
        <span>Typed update</span>
      </div>
      <p className="muted small">
        This writes to the canonical contract. It is not a free-form override: every value receives provenance and is revalidated before firmware authority changes.
      </p>
      <form onSubmit={submit} className="contract-form">
        <label>
          Signal ID
          <input value={draft.signalId} onChange={(event) => update("signalId", event.target.value)} placeholder="enable" />
        </label>
        <label>
          Contact ID
          <input value={draft.contactId} onChange={(event) => update("contactId", event.target.value)} placeholder="J_LOGIC.1" />
        </label>
        <label>
          Connector
          <input value={draft.connectorRef} onChange={(event) => update("connectorRef", event.target.value)} placeholder="J_LOGIC" />
        </label>
        <label>
          Physical pin
          <input value={draft.pinNumber} onChange={(event) => update("pinNumber", event.target.value)} placeholder="1" />
        </label>
        <label>
          Direction
          <select value={draft.direction} onChange={(event) => update("direction", event.target.value)}>
            <option value="input">Input to donor</option>
            <option value="output">Output from donor</option>
            <option value="bidirectional">Bidirectional</option>
          </select>
        </label>
        <label>
          Maximum logic voltage (V)
          <input type="number" min="0" step="0.01" value={draft.voltageMax} onChange={(event) => update("voltageMax", event.target.value)} />
        </label>
        <label>
          Active level
          <select value={draft.activeLevel} onChange={(event) => update("activeLevel", event.target.value)}>
            <option value="high">Active high</option>
            <option value="low">Active low</option>
          </select>
        </label>
        <label>
          Controller pin
          <input value={draft.controllerPin} onChange={(event) => update("controllerPin", event.target.value)} placeholder="GPIO16" />
        </label>
        <label className="contract-form__wide">
          Evidence method
          <input value={draft.method} onChange={(event) => update("method", event.target.value)} placeholder="DMM plus protected stimulus" />
        </label>
        <label className="contract-form__wide">
          Notes
          <textarea value={draft.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Probe points, resistor value, observed response, instrument ID…" />
        </label>
        <div className="contract-form__actions contract-form__wide">
          <span className="mono small">Gate: {gate.gate_id}</span>
          <button type="submit" className="primary" disabled={!required || submitting}>
            {submitting ? "Persisting…" : "Save evidenced signal"}
          </button>
        </div>
      </form>
      {result ? (
        <p className={result.ok ? "success small" : "error small"} role="status">{result.message}</p>
      ) : null}
    </section>
  );
}

function InterfaceDetail({ item, benchSession, onContractUpdate, onToast }) {
  if (!item) {
    return (
      <div className="evidence-empty">
        <strong>No interface selected</strong>
        <p>Select a donor interface to inspect its authority boundary.</p>
      </div>
    );
  }
  const contract = item.interface_contract || {};
  const blockers = item.blockers || contract.unresolved_fields || [];
  const references = contract.reference_equivalents || [];
  const contacts = contract.contacts || [];
  const signals = contract.signals || [];
  const recipe = item.bench_recipe;

  return (
    <div className="evidence-detail">
      <div className="evidence-detail__header">
        <div>
          <p className="eyebrow">{contract.board_id || "Donor board"}</p>
          <h3>{titleCase(contract.functional_role || contract.block_id)}</h3>
          <p className="mono small">{contract.virtual_module_id || contract.interface_id}</p>
        </div>
        <span className={`evidence-state evidence-state--${item.compile_status === "ready" ? "ok" : "blocked"}`}>
          {item.compile_status === "ready" ? "Firmware-ready" : "Generation blocked"}
        </span>
      </div>

      {item.legacy_fallback ? (
        <div className="evidence-callout evidence-callout--warn">
          <strong>Legacy donor binding detected</strong>
          <p>This build predates the canonical interface contract. It is displayed conservatively and remains blocked.</p>
        </div>
      ) : null}

      <div className="evidence-detail-grid">
        <section>
          <h4>Known contacts</h4>
          {contacts.length ? (
            <div className="contact-grid">
              {contacts.map((contact) => (
                <div key={contact.contact_id} className="contact-card">
                  <strong>{contact.connector_ref || contact.label || contact.contact_id}</strong>
                  <span>{contact.pin_number ? `Pin ${contact.pin_number}` : "Pin unresolved"}</span>
                  <small>{contact.side || "side unknown"}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small">No contacts have been evidenced.</p>
          )}
        </section>

        <section>
          <h4>Control signals</h4>
          {signals.length ? (
            <div className="signal-list">
              {signals.map((signal) => (
                <div key={signal.signal_id} className="signal-row">
                  <strong>{signal.signal_id}</strong>
                  <span>{titleCase(signal.direction)}</span>
                  <span>{signal.controller_pin?.value || "MCU pin unresolved"}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted small">Signal semantics are intentionally unresolved.</p>
          )}
        </section>
      </div>

      {references.length ? (
        <section className="evidence-section">
          <div className="section-heading">
            <h4>Functional references</h4>
            <span>Reference only</span>
          </div>
          <div className="reference-list">
            {references.map((reference) => (
              <div key={`${reference.module_id}-${reference.relationship}`} className="reference-row">
                <strong>{reference.module_id}</strong>
                <span>{titleCase(reference.relationship)}</span>
                <small>
                  {reference.electrical_contract_inherited === false
                    ? "Electrical pins and limits are not inherited"
                    : "Review inherited semantics"}
                </small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="evidence-section">
        <div className="section-heading">
          <h4>Open authority blockers</h4>
          <span>{blockers.length}</span>
        </div>
        {blockers.length ? (
          <div className="blocker-grid">
            {blockers.map((blocker) => (
              <span key={blocker} className="blocker-chip">{blocker}</span>
            ))}
          </div>
        ) : (
          <p className="muted small">No unresolved interface fields.</p>
        )}
      </section>

      <ContractEditor item={item} benchSession={benchSession} onContractUpdate={onContractUpdate} onToast={onToast} />

      {recipe?.phases?.length ? (
        <section className="evidence-section">
          <div className="section-heading">
            <h4>Required measurement sequence</h4>
            <span>{recipe.phases.length} phases</span>
          </div>
          <ol className="evidence-phase-list">
            {recipe.phases.map((phase, index) => (
              <li key={phase.phase_id}>
                <div className="phase-index">{String(index + 1).padStart(2, "0")}</div>
                <div>
                  <strong>{phase.title}</strong>
                  <ul>
                    {(phase.instructions || []).map((instruction) => <li key={instruction}>{instruction}</li>)}
                  </ul>
                  {(phase.measurements || []).length ? (
                    <div className="measurement-strip">
                      {phase.measurements.map((measurement) => (
                        <span key={measurement.measurement_id}>
                          {measurement.description}
                          {measurement.unit ? ` · ${measurement.unit}` : ""}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

export default function EvidenceWorkbenchPanel({ session, onGoBench, onGoVerify, onContractUpdate, onToast }) {
  const truth = useMemo(() => deriveEvidenceTruth(session), [session]);
  const [selectedId, setSelectedId] = useState(null);
  if (!truth.applicable) return null;

  const selected =
    truth.interfaces.find((item) => item?.interface_contract?.interface_id === selectedId) ||
    truth.interfaces[0] ||
    null;

  return (
    <section className="evidence-workbench" data-testid="evidence-workbench">
      <header className="evidence-hero">
        <div>
          <p className="eyebrow">Evidence authority</p>
          <h2>Know what the donor exposes before the compiler acts</h2>
          <p>
            Hardware Splicer may use a catalog part as a functional reference, but it cannot inherit pins, voltage limits,
            polarity, or firmware behavior without accepted evidence.
          </p>
        </div>
        <div className="evidence-hero__actions">
          <button type="button" className="ghost" onClick={() => downloadJson("hardware-splicer-evidence.json", truth.integrations || truth)}>
            Export evidence JSON
          </button>
          <button type="button" className="secondary" onClick={onGoVerify}>Review compiled design</button>
          <button type="button" className="primary" onClick={onGoBench}>Record bench evidence</button>
        </div>
      </header>

      <div className={`evidence-boundary evidence-boundary--${evidenceTone(truth.state)}`}>
        <div>
          <span className="authority-dot" aria-hidden />
          <div>
            <strong>{truth.label}</strong>
            <p>{truth.detail}</p>
          </div>
        </div>
        <code>{truth.claimBoundary}</code>
      </div>

      <div className="evidence-metrics">
        <Metric label="Interfaces" value={truth.interfaceCount} detail="Donor functional boundaries" />
        <Metric label="Unresolved fields" value={truth.unresolvedFieldCount} detail="Must be observed or measured" tone={truth.unresolvedFieldCount ? "warn" : "ok"} />
        <Metric label="Firmware" value={truth.firmwareAuthorized ? "Authorized" : "Blocked"} detail="PlatformIO generation gate" tone={truth.firmwareAuthorized ? "ok" : "fail"} />
        <Metric label="Power-on" value={truth.powerAuthorized ? "Authorized" : "Blocked"} detail="Physical bench authority" tone={truth.powerAuthorized ? "ok" : "fail"} />
      </div>

      <div className="backend-readiness-grid">
        <BackendCard name="tscircuit projection" row={truth.backendReadiness.tscircuit} />
        <BackendCard name="PlatformIO firmware" row={truth.backendReadiness.platformio} />
        <BackendCard name="KiBot manufacturing" row={truth.backendReadiness.kibot} />
      </div>

      <div className="evidence-workbench__body">
        <aside className="evidence-interface-list" aria-label="Donor interfaces">
          <div className="section-heading">
            <h3>Donor interfaces</h3>
            <span>{truth.interfaces.length}</span>
          </div>
          {truth.interfaces.length ? truth.interfaces.map((item) => {
            const id = item?.interface_contract?.interface_id;
            return <InterfaceListItem key={id || item?.interface_contract?.virtual_module_id} item={item} active={selected === item} onSelect={() => setSelectedId(id)} />;
          }) : (
            <div className="evidence-empty compact">
              <strong>No canonical interface contract</strong>
              <p>Regenerate the salvage package with the evidence-first stack.</p>
            </div>
          )}
        </aside>
        <InterfaceDetail item={selected} benchSession={session.benchSession} onContractUpdate={onContractUpdate} onToast={onToast} />
      </div>
    </section>
  );
}
