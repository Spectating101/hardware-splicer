// The record a non-geometric question is about, drawn in its own form: a strategy as a comparison
// of its options, a simulation as its scenarios. Values are the record's own; nothing is scored.

const money = (value) => (value == null ? "not costed" : `$${Number(value).toFixed(2)}`);
const words = (text) => String(text ?? "").replace(/_/g, " ");
const num = (value, digits = 1, unit = "") => (value == null ? "–" : `${Number(value).toFixed(digits)}${unit}`);

function StrategyMatrix({ record, focus }) {
  const roles = (id) => Object.entries(record.decision ?? {})
    .filter(([, value]) => value === id).map(([role]) => words(role).replace(/^selected for /, ""));
  const rows = [
    ["Known cost", (option) => money(option.known_usd)],
    ["Cost complete", (option) => (option.cost_complete ? "yes" : `no, ${option.missing.length} not costed`)],
    ["Engineering", (option) => words(option.engineering_status) || "–"],
    ["Procurement", (option) => words(option.procurement_status) || "–"],
    ["Risk", (option) => words(option.risk) || "–"],
    ["Chosen as", (option) => roles(option.id).join("; ") || "–"],
  ];
  return (
    <>
      <h2>Build, buy or salvage: the options compared</h2>
      {record.objective && <p className="dv-canvas-lede">{record.objective}</p>}
      <div className="dv-canvas-scroll">
        <table className="dv-matrix">
          <thead>
            <tr><th scope="col"><span className="dv-visually-hidden">Measure</span></th>
              {record.options.map((option) => (
                <th key={option.id} scope="col" data-focus={option.id === focus || undefined}
                  data-chosen={roles(option.id).length > 0 || undefined}>{option.label}</th>
              ))}</tr>
          </thead>
          <tbody>
            {rows.map(([label, cell]) => (
              <tr key={label}><th scope="row">{label}</th>
                {record.options.map((option) => (
                  <td key={option.id} data-focus={option.id === focus || undefined}>{cell(option)}</td>
                ))}</tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="dv-canvas-note">
        Procurement approved: {record.decision?.procurement_approved ? "yes" : "no"}
        {record.constraints?.physical_build_authorized === false ? " · physical build not authorized" : ""}
        {" · costs are the record's known prices; uncosted items are not estimated"}
      </p>
    </>
  );
}

function SimulationTable({ record }) {
  const columns = [
    ["Duration", (m) => num(m.seconds, 0, " s")],
    ["Hover error", (m) => (m.hover_error_m == null ? "–" : `${(m.hover_error_m * 100).toFixed(1)} cm`)],
    ["Max tilt", (m) => num(m.max_tracking_tilt_deg, 1, "°")],
    ["Peak current (est.)", (m) => num(m.peak_current_a_est, 2, " A")],
    ["Energy (est.)", (m) => num(m.consumed_mah_est, 1, " mAh")],
  ];
  return (
    <>
      <h2>Simulated missions</h2>
      <p className="dv-canvas-lede">Each scenario as the simulation ran it. Simulation only: nothing here has flown.</p>
      <div className="dv-canvas-scroll">
        <table className="dv-matrix">
          <thead>
            <tr><th scope="col">Scenario</th><th scope="col">Expected</th><th scope="col">Outcome</th>
              {columns.map(([label]) => <th key={label} scope="col">{label}</th>)}</tr>
          </thead>
          <tbody>
            {record.scenarios.map((row) => (
              <tr key={row.id}>
                <th scope="row">{words(row.id)}{row.extra_mass_g ? ` (+${row.extra_mass_g} g)` : ""}</th>
                <td>{words(row.expected)}</td>
                <td>{row.accepted ? "as expected" : `not as expected${row.checks_failed.length ? `: ${row.checks_failed.map(words).join(", ")}` : ""}`}
                  {row.motor_failure && row.metrics.fault_detected ? " · fault detected" : ""}</td>
                {columns.map(([label, cell]) => <td key={label}>{cell(row.metrics)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {record.scope_limits?.length > 0 && <details className="dv-canvas-limits">
        <summary>What the simulation leaves out ({record.scope_limits.length})</summary>
        <ul>{record.scope_limits.map((line) => <li key={line}>{line}</li>)}</ul>
      </details>}
    </>
  );
}

export function EvidenceCanvas({ canvas, onClose }) {
  if (!canvas) return null;
  return (
    <section className="dv-canvas" aria-label="Record" data-stage-edge="right">
      <button type="button" className="dv-canvas-close" onClick={onClose} aria-label="Hide the record">×</button>
      {canvas.kind === "strategy" && <StrategyMatrix record={canvas.record} focus={canvas.focus} />}
      {canvas.kind === "simulation" && <SimulationTable record={canvas.record} />}
    </section>
  );
}
