import { useMemo, useState } from "react";

import { netlistCompile } from "../api.js";
import { inspectCircuitJson } from "../circuitJsonApi.js";
import LabResultCard from "./LabResultCard.jsx";
import "./CircuitJsonImportPanel.css";

const SAMPLE = JSON.stringify(
  [
    {
      type: "source_component",
      source_component_id: "source_component_0",
      ftype: "simple_resistor",
      name: "R1",
      resistance: 1000,
      display_resistance: "1kΩ",
    },
    {
      type: "source_component",
      source_component_id: "source_component_1",
      ftype: "simple_diode",
      name: "LED1",
    },
    {
      type: "source_port",
      source_port_id: "source_port_0",
      source_component_id: "source_component_0",
      name: "pin2",
      pin_number: 2,
    },
    {
      type: "source_port",
      source_port_id: "source_port_1",
      source_component_id: "source_component_1",
      name: "anode",
      pin_number: 1,
    },
    {
      type: "source_trace",
      source_trace_id: "source_trace_0",
      connected_source_port_ids: ["source_port_0", "source_port_1"],
      connected_source_net_ids: [],
      display_name: "R1 to LED1",
    },
  ],
  null,
  2,
);

function StatusSummary({ inspection }) {
  if (!inspection) return null;
  const summary = inspection.summary || {};
  return (
    <div className={`circuit-json-import__summary circuit-json-import__summary--${inspection.status}`}>
      <div>
        <span className="eyebrow">{String(inspection.status || "unknown").replaceAll("_", " ")}</span>
        <strong>{inspection.headline}</strong>
      </div>
      <span className="chip small">Authority: {inspection.authority || "proposed"}</span>
      <dl>
        <div><dt>Components</dt><dd>{summary.component_count || 0}</dd></div>
        <div><dt>Nets</dt><dd>{summary.net_count || 0}</dd></div>
        <div><dt>Unresolved</dt><dd>{summary.unresolved_count || 0}</dd></div>
        <div><dt>Incomplete nets</dt><dd>{summary.single_pin_net_count || 0}</dd></div>
      </dl>
    </div>
  );
}

function Diagnostics({ inspection }) {
  if (!inspection) return null;
  const diagnostics = inspection.diagnostics || {};
  const rows = [
    ["Unresolved component ports", diagnostics.unresolved_ports || []],
    ["Unresolved trace ports", diagnostics.unresolved_trace_ports || []],
    ["Ambiguous traces", diagnostics.ambiguous_traces || []],
    ["Single-pin nets", diagnostics.single_pin_nets || []],
    ["Upstream diagnostics", diagnostics.upstream_diagnostics || []],
  ].filter(([, items]) => items.length > 0);
  if (!rows.length) return <p className="small muted">No import diagnostics were raised.</p>;

  return (
    <details className="circuit-json-import__diagnostics" open>
      <summary>Import diagnostics</summary>
      {rows.map(([label, items]) => (
        <div key={label}>
          <strong>{label} ({items.length})</strong>
          <pre>{JSON.stringify(items.slice(0, 8), null, 2)}</pre>
        </div>
      ))}
    </details>
  );
}

export default function CircuitJsonImportPanel({ onViewBoard }) {
  const [text, setText] = useState(SAMPLE);
  const [inspection, setInspection] = useState(null);
  const [compileResult, setCompileResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const documents = useMemo(() => {
    try {
      const parsed = JSON.parse(text);
      return Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }, [text]);

  const inspect = async () => {
    setBusy("inspect");
    setError("");
    setCompileResult(null);
    try {
      if (!documents) throw new Error("Paste a valid Circuit JSON array.");
      setInspection(await inspectCircuitJson(documents));
    } catch (err) {
      setInspection(null);
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const compile = async () => {
    setBusy("compile");
    setError("");
    setCompileResult(null);
    try {
      if (!documents) throw new Error("Paste a valid Circuit JSON array.");
      const current = inspection || (await inspectCircuitJson(documents));
      setInspection(current);
      if (!current.compilable) throw new Error(current.headline || "Circuit JSON is not compilable.");
      const result = await netlistCompile({
        circuitJson: documents,
        buildId: "generic_low_voltage_build",
        exportGerber: false,
      });
      setCompileResult({
        ...result,
        interchange_inspection: current,
        via: "upstream_circuit_json",
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="card circuit-json-import" data-testid="circuit-json-import-panel">
      <div>
        <p className="eyebrow">tscircuit interoperability</p>
        <h3>Import upstream Circuit JSON</h3>
        <p className="muted">
          Inspect real source components, ports, named nets, and traces before compiling them into the Hardware Splicer workflow.
        </p>
      </div>

      <textarea
        className="circuit-json-import__editor mono"
        rows={13}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setInspection(null);
          setCompileResult(null);
        }}
        aria-label="Circuit JSON documents"
        spellCheck={false}
      />
      {!documents && <p className="error">The editor must contain a JSON array.</p>}

      <div className="lab-actions">
        <button type="button" className="secondary" disabled={Boolean(busy) || !documents} onClick={inspect}>
          {busy === "inspect" ? "Inspecting…" : "Inspect source graph"}
        </button>
        <button type="button" className="primary" disabled={Boolean(busy) || !documents} onClick={compile}>
          {busy === "compile" ? "Compiling…" : "Compile accepted graph → KiCad"}
        </button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      <StatusSummary inspection={inspection} />
      <Diagnostics inspection={inspection} />
      <LabResultCard
        title="Upstream Circuit JSON compile"
        subtitle="Source graph → Hardware Splicer netlist → KiCad"
        payload={compileResult}
        onViewBoard={onViewBoard}
      />
    </section>
  );
}
