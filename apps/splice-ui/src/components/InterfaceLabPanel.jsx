import { useEffect, useState } from "react";
import {
  composeCanvas,
  composePhrase,
  fetchNetlistFixture,
  fetchNetlistFixtures,
  netlistCompile,
} from "../api.js";
import LabResultCard from "./LabResultCard.jsx";
import IntegrationsCatalog from "./IntegrationsPanel.jsx";

const DEMO_NODES = [
  { id: "n1", moduleId: "usb-power-5v" },
  { id: "n2", moduleId: "esp32-devkit" },
  { id: "n3", moduleId: "dht22" },
];

const DEMO_WIRES = [
  { from: { nodeId: "n1", pinId: "5V" }, to: { nodeId: "n2", pinId: "VIN" } },
  { from: { nodeId: "n1", pinId: "GND" }, to: { nodeId: "n2", pinId: "GND" } },
  { from: { nodeId: "n2", pinId: "3V3" }, to: { nodeId: "n3", pinId: "VCC" } },
  { from: { nodeId: "n2", pinId: "GND" }, to: { nodeId: "n3", pinId: "GND" } },
  { from: { nodeId: "n2", pinId: "GPIO4" }, to: { nodeId: "n3", pinId: "DATA" } },
];

const PATH_HELP = [
  {
    id: "llm-first",
    title: "LLM-first compose",
    body: "Natural-language goal → Qwen module pick + DRC feedback loop. Same spine as MCP hs_compose with allow_llm_first.",
  },
  {
    id: "canvas",
    title: "compose-canvas",
    body: "Wire a module graph in memory, then compile to KiCad. This mirrors Circuit.AI-style editing without building a browser ECAD suite.",
  },
  {
    id: "circuit-json",
    title: "circuit-json",
    body: "tscircuit-style JSON interchange. Good for agents and web-native editors that emit circuit-json.",
  },
  {
    id: "kicad-netlist",
    title: "KiCad netlist",
    body: "S-expression netlist from SKiDL, atopile, or KiCad. Same compile spine — adapter proving ground, not the main product wizard.",
  },
];

function fixtureLabel(row) {
  if (row.description) return row.description;
  if (row.module_ids?.length) return row.module_ids.join(" + ");
  return row.id;
}

const LLM_DEMO_PHRASE =
  "USB-powered ESP32 soil moisture monitor with pump driver and status LED for a small plant watering carrier";

export default function InterfaceLabPanel({ llmPolicy, onOpenDesignPreview, onRunFullDemo }) {
  const [fixtures, setFixtures] = useState([]);
  const [fixtureId, setFixtureId] = useState("usb_esp_dht22");
  const [canvasWire, setCanvasWire] = useState(null);
  const [canvasCompile, setCanvasCompile] = useState(null);
  const [llmWire, setLlmWire] = useState(null);
  const [llmCompile, setLlmCompile] = useState(null);
  const [llmPhrase, setLlmPhrase] = useState(LLM_DEMO_PHRASE);
  const [llmFirst, setLlmFirst] = useState(true);
  const [llmError, setLlmError] = useState("");
  const [netlistResult, setNetlistResult] = useState(null);
  const [canvasError, setCanvasError] = useState("");
  const [netlistError, setNetlistError] = useState("");
  const [busy, setBusy] = useState("");
  const [pasteNetlist, setPasteNetlist] = useState("");
  const [showPaste, setShowPaste] = useState(false);

  const llmReady = Boolean(llmPolicy?.qwen_llm_first);

  useEffect(() => {
    if (llmReady) setLlmFirst(true);
  }, [llmReady]);

  useEffect(() => {
    fetchNetlistFixtures()
      .then((payload) => {
        const rows = payload.fixtures || [];
        setFixtures(rows);
        const preferred = rows.find((row) => row.id === "usb_esp_dht22") || rows[0];
        if (preferred?.id) setFixtureId(preferred.id);
      })
      .catch(() => {});
  }, []);

  const runLlmCompose = async (wireOnly) => {
    setBusy(wireOnly ? "llm-wire" : "llm-compile");
    setLlmError("");
    if (wireOnly) setLlmWire(null);
    else setLlmCompile(null);
    try {
      const payload = await composePhrase(llmPhrase.trim(), {
        allowLlmFirst: llmFirst,
        wireOnly,
        exportGerber: false,
      });
      if (wireOnly) setLlmWire(payload);
      else setLlmCompile(payload);
    } catch (err) {
      setLlmError(err.message);
    } finally {
      setBusy("");
    }
  };

  const runCanvas = async (wireOnly) => {
    setBusy(wireOnly ? "canvas-wire" : "canvas-compile");
    if (wireOnly) {
      setCanvasError("");
    } else {
      setCanvasError("");
      setCanvasCompile(null);
    }
    try {
      const payload = await composeCanvas(DEMO_NODES, DEMO_WIRES, { wireOnly, exportGerber: false });
      if (wireOnly) setCanvasWire(payload);
      else setCanvasCompile(payload);
    } catch (err) {
      if (wireOnly) setCanvasError(err.message);
      else setCanvasError(err.message);
    } finally {
      setBusy("");
    }
  };

  const runKicadNetlist = async () => {
    setBusy("kicad-netlist");
    setNetlistError("");
    setNetlistResult(null);
    try {
      const fixture = await fetchNetlistFixture(fixtureId);
      const payload = await netlistCompile({
        kicadNetlistText: fixture.kicad_netlist_text,
        buildId: "generic_low_voltage_build",
        exportGerber: false,
      });
      setNetlistResult({ ...payload, fixture_label: fixture.description, via: "kicad_netlist" });
    } catch (err) {
      setNetlistError(err.message);
    } finally {
      setBusy("");
    }
  };

  const runPastedNetlist = async () => {
    setBusy("paste-netlist");
    setNetlistError("");
    setNetlistResult(null);
    try {
      const payload = await netlistCompile({
        kicadNetlistText: pasteNetlist,
        buildId: "generic_low_voltage_build",
        exportGerber: false,
      });
      setNetlistResult({ ...payload, fixture_label: "Pasted KiCad netlist", via: "kicad_netlist_paste" });
    } catch (err) {
      setNetlistError(err.message);
    } finally {
      setBusy("");
    }
  };

  const selectedFixture = fixtures.find((row) => row.id === fixtureId);
  const isKicadFixture = selectedFixture?.type === "kicad_netlist";

  const runCircuitJson = async () => {
    setBusy("circuit-json");
    setNetlistError("");
    setNetlistResult(null);
    try {
      const fixture = await fetchNetlistFixture(fixtureId);
      const payload = await netlistCompile({
        circuitJson: fixture.circuit_json,
        buildId: "generic_low_voltage_build",
        exportGerber: false,
      });
      setNetlistResult({ ...payload, fixture_label: fixture.description, via: "circuit_json" });
    } catch (err) {
      setNetlistError(err.message);
    } finally {
      setBusy("");
    }
  };

  const openPreview = (ctx) => {
    if (!onOpenDesignPreview) return;
    onOpenDesignPreview({
      buildDir: ctx.buildDir,
      title: ctx.title || "Interface lab compile",
      qualityHint: ctx.truth,
    });
  };

  return (
    <div className="panel-stack">
      <section className="card lab-hero">
        <p className="eyebrow">Interface lab · v1.1 preview</p>
        <h2>Adapter proving ground — not the main product path</h2>
        <p className="muted">
          Borrowed OSS interchange layers feed the same compile spine. Use this to test imports; use the project wizard
          for donor bring-up, gates, and PROJECT_PACKAGE.
        </p>
        <ul className="lab-path-help">
          {PATH_HELP.map((row) => (
            <li key={row.id}>
              <strong className="mono">{row.title}</strong> — {row.body}
            </li>
          ))}
        </ul>
        {onRunFullDemo && (
          <button type="button" className="secondary" onClick={onRunFullDemo}>
            Run repair-café demo build →
          </button>
        )}
      </section>

      <section className="card lab-llm-card">
        <h3>0 · LLM-first compose</h3>
        <p className="muted">
          Describe a carrier in plain English. With Qwen configured, the engine runs LLM-first module selection and
          compile — otherwise it falls back to heuristic scratch compose.
        </p>
        <textarea
          className="field-textarea"
          rows={4}
          value={llmPhrase}
          onChange={(e) => setLlmPhrase(e.target.value)}
          placeholder="Example: ESP32 plant monitor with soil sensor, pump MOSFET, and USB power input"
        />
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={llmFirst}
            disabled={!llmReady}
            onChange={(e) => setLlmFirst(e.target.checked)}
          />
          <span>
            Allow LLM-first compose{" "}
            {llmReady ? "(Qwen ready)" : "(offline — heuristic scratch only)"}
          </span>
        </label>
        <div className="lab-actions">
          <button type="button" className="secondary" disabled={Boolean(busy) || llmPhrase.trim().length < 12} onClick={() => runLlmCompose(true)}>
            {busy === "llm-wire" ? "Wiring…" : "Wire modules (phrase)"}
          </button>
          <button type="button" className="primary" disabled={Boolean(busy) || llmPhrase.trim().length < 12} onClick={() => runLlmCompose(false)}>
            {busy === "llm-compile" ? "Compiling…" : "LLM-first compile → KiCad"}
          </button>
        </div>
        <LabResultCard
          title="LLM wire result"
          payload={llmWire}
          error={llmError && !llmWire ? llmError : ""}
        />
        <LabResultCard
          title="LLM-first compile"
          subtitle={llmCompile?.mode === "llm_first" ? `compose_mode: ${llmCompile.compose_mode || "qwen"}` : "scratch fallback"}
          payload={llmCompile}
          error={llmError && !llmCompile ? llmError : ""}
          onViewBoard={(ctx) => openPreview({ ...ctx, title: "LLM-first compose" })}
        />
      </section>

      <section className="card">
        <h3>1 · Canvas → compose</h3>
        <p className="muted">
          USB power, ESP32, and DHT22 modules — same graph path as Circuit.AI. Wire first, then compile to KiCad.
        </p>
        <div className="lab-actions">
          <button type="button" className="secondary" disabled={Boolean(busy)} onClick={() => runCanvas(true)}>
            {busy === "canvas-wire" ? "Wiring…" : "Step A — Wire graph"}
          </button>
          <button type="button" className="primary" disabled={Boolean(busy)} onClick={() => runCanvas(false)}>
            {busy === "canvas-compile" ? "Compiling…" : "Step B — Compile to KiCad"}
          </button>
        </div>
        <LabResultCard
          title="Wire-only result"
          payload={canvasWire}
          error={canvasError && !canvasWire ? canvasError : ""}
        />
        <LabResultCard
          title="KiCad compile result"
          subtitle="USB + ESP32 + DHT22 carrier"
          payload={canvasCompile}
          error={canvasError && !canvasCompile ? canvasError : ""}
          onViewBoard={(ctx) => openPreview({ ...ctx, title: "Canvas compile — USB/ESP32/DHT22" })}
        />
      </section>

      <section className="card">
        <h3>2 · Interchange → netlist-compile</h3>
        <p className="muted">
          circuit-json (tscircuit) or KiCad netlist (SKiDL-class tools) feed the same engine. Pick a fixture, compile,
          preview the board.
        </p>
        <div className="lab-actions">
          <select value={fixtureId} onChange={(e) => setFixtureId(e.target.value)} className="lab-select">
            {fixtures.map((row) => (
              <option key={row.id} value={row.id}>
                {row.id} — {fixtureLabel(row)}
              </option>
            ))}
          </select>
          {isKicadFixture ? (
            <button type="button" className="primary" disabled={Boolean(busy)} onClick={runKicadNetlist}>
              {busy === "kicad-netlist" ? "Compiling…" : "Compile KiCad netlist"}
            </button>
          ) : (
            <button type="button" className="primary" disabled={Boolean(busy)} onClick={runCircuitJson}>
              {busy === "circuit-json" ? "Compiling…" : "Compile circuit-json"}
            </button>
          )}
        </div>
        <LabResultCard
          title={isKicadFixture ? "KiCad netlist compile" : "circuit-json compile"}
          subtitle={netlistResult?.fixture_label || fixtureId}
          payload={netlistResult}
          error={netlistError}
          onViewBoard={(ctx) =>
            openPreview({
              ...ctx,
              title: `${netlistResult?.via || "interchange"} — ${fixtureId}`,
            })
          }
        />
      </section>

      <section className="card">
        <h3>3 · Paste KiCad netlist (SKiDL / atopile export)</h3>
        <p className="muted">
          Export a KiCad netlist from SKiDL, atopile, or KiCad Eeschema and compile through the same spine — no fixture
          required.
        </p>
        <button type="button" className="ghost small" onClick={() => setShowPaste((value) => !value)}>
          {showPaste ? "Hide paste box" : "Paste netlist…"}
        </button>
        {showPaste && (
          <>
            <textarea
              className="lab-netlist-paste"
              rows={8}
              placeholder="(export (version &quot;E&quot;) (components …"
              value={pasteNetlist}
              onChange={(e) => setPasteNetlist(e.target.value)}
            />
            <div className="lab-actions">
              <button
                type="button"
                className="primary"
                disabled={Boolean(busy) || pasteNetlist.trim().length < 20}
                onClick={runPastedNetlist}
              >
                {busy === "paste-netlist" ? "Compiling…" : "Compile pasted netlist"}
              </button>
            </div>
          </>
        )}
        {netlistResult?.via === "kicad_netlist_paste" && (
          <LabResultCard
            title="Pasted netlist compile"
            subtitle={netlistResult.fixture_label}
            payload={netlistResult}
            error={netlistError}
            onViewBoard={(ctx) => openPreview({ ...ctx, title: "Pasted KiCad netlist" })}
          />
        )}
      </section>

      <IntegrationsCatalog />
    </div>
  );
}
