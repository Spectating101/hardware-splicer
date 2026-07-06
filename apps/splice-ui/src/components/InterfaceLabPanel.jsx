import { useEffect, useState } from "react";
import {
  composeCanvas,
  fetchNetlistFixture,
  fetchNetlistFixtures,
  netlistCompile,
} from "../api.js";

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

export default function InterfaceLabPanel() {
  const [fixtures, setFixtures] = useState([]);
  const [fixtureId, setFixtureId] = useState("usb_esp_dht22");
  const [canvasResult, setCanvasResult] = useState(null);
  const [netlistResult, setNetlistResult] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchNetlistFixtures()
      .then((payload) => {
        const rows = payload.fixtures || [];
        setFixtures(rows);
        if (rows[0]?.id) setFixtureId(rows[0].id);
      })
      .catch(() => {});
  }, []);

  const runCanvas = async (wireOnly) => {
    setBusy(wireOnly ? "canvas-wire" : "canvas-compile");
    setError("");
    try {
      const payload = await composeCanvas(DEMO_NODES, DEMO_WIRES, { wireOnly, exportGerber: false });
      setCanvasResult(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const runCircuitJson = async () => {
    setBusy("circuit-json");
    setError("");
    try {
      const fixture = await fetchNetlistFixture(fixtureId);
      const payload = await netlistCompile({
        circuitJson: fixture.circuit_json,
        buildId: "generic_low_voltage_build",
        exportGerber: false,
      });
      setNetlistResult(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const canvasQuality = canvasResult?.design_quality || {};
  const netlistQuality = netlistResult?.design_quality || {};

  return (
    <div className="panel-stack">
      <section className="card">
        <h3>Interface lab</h3>
        <p className="muted">
          Spike: borrowed interfaces on the existing engine — <code>/v1/compose-canvas</code> and{" "}
          <code>/v1/netlist-compile</code> (circuit-json).
        </p>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h3>Canvas → compile</h3>
        <p className="muted">USB + ESP32 + DHT22 module graph through the same compose spine as Circuit.AI.</p>
        <div className="lab-actions">
          <button type="button" className="secondary" disabled={Boolean(busy)} onClick={() => runCanvas(true)}>
            {busy === "canvas-wire" ? "Wiring…" : "Wire-only graph"}
          </button>
          <button type="button" className="primary" disabled={Boolean(busy)} onClick={() => runCanvas(false)}>
            {busy === "canvas-compile" ? "Compiling…" : "Compile to KiCad"}
          </button>
        </div>
        {canvasResult && (
          <pre className="lab-output">
            {JSON.stringify(
              {
                wire_only: canvasResult.wire_only,
                node_count: canvasResult.graph?.nodes?.length,
                wire_count: canvasResult.graph?.wires?.length,
                kicad_drc_errors: canvasQuality.kicad_drc_errors,
                kicad_drc_warnings: canvasQuality.kicad_drc_warnings,
                copper_tier: canvasQuality.copper_tier,
                build_dir: canvasResult.build_dir || canvasResult.out_dir,
              },
              null,
              2,
            )}
          </pre>
        )}
      </section>

      <section className="card">
        <h3>circuit-json → netlist-compile</h3>
        <p className="muted">Fixture roundtrip via tscircuit-style circuit-json interchange.</p>
        <div className="lab-actions">
          <select value={fixtureId} onChange={(e) => setFixtureId(e.target.value)} className="lab-select">
            {fixtures.map((row) => (
              <option key={row.id} value={row.id}>
                {row.id} — {row.description}
              </option>
            ))}
          </select>
          <button type="button" className="primary" disabled={Boolean(busy)} onClick={runCircuitJson}>
            {busy === "circuit-json" ? "Compiling…" : "Compile fixture"}
          </button>
        </div>
        {netlistResult && (
          <pre className="lab-output">
            {JSON.stringify(
              {
                fixture_id: fixtureId,
                kicad_drc_errors: netlistQuality.kicad_drc_errors,
                kicad_drc_warnings: netlistQuality.kicad_drc_warnings,
                copper_tier: netlistQuality.copper_tier,
                circuit_json_path: netlistResult.circuit_json,
                build_dir: netlistResult.build_dir || netlistResult.out_dir,
              },
              null,
              2,
            )}
          </pre>
        )}
      </section>
    </div>
  );
}
