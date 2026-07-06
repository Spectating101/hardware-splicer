import { useEffect, useState } from "react";
import {
  composeCanvas,
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

const STEPS = [
  "Wire a module graph (canvas → compose spine).",
  "Compile to KiCad and open the board in the Design preview.",
  "Or import circuit-json and compile through the same engine.",
];

export default function InterfaceLabPanel({ onOpenDesignPreview, onRunFullDemo }) {
  const [fixtures, setFixtures] = useState([]);
  const [fixtureId, setFixtureId] = useState("usb_esp_dht22");
  const [canvasWire, setCanvasWire] = useState(null);
  const [canvasCompile, setCanvasCompile] = useState(null);
  const [netlistResult, setNetlistResult] = useState(null);
  const [canvasError, setCanvasError] = useState("");
  const [netlistError, setNetlistError] = useState("");
  const [busy, setBusy] = useState("");

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
        <p className="eyebrow">Interface lab</p>
        <h2>See the engine through borrowed OSS paths</h2>
        <p className="muted">
          This is not a Flux clone. It proves the same compile spine accepts canvas graphs and circuit-json interchange,
          then shows the KiCad result in KiCanvas.
        </p>
        <ol className="lab-steps">
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        {onRunFullDemo && (
          <button type="button" className="secondary" onClick={onRunFullDemo}>
            Run repair-café demo build →
          </button>
        )}
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
                {row.id} — {row.description}
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

      <IntegrationsCatalog />
    </div>
  );
}
