/**
 * Surfaced only when canonical HS package reports a blocked rover-power review.
 * No local buttons can authorize physical operation or invent measurements.
 */
export default function RoverPowerEvidencePanel({ report }) {
  if (!report || report.status === "not_applicable") return null;
  const declared = report.declared || {};
  const measured = report.measured || {};
  const blockers = Array.isArray(report.blockers) ? report.blockers : [];
  const actions = Array.isArray(report.next_actions) ? report.next_actions : [];
  return (
    <section className="card honesty-card honesty-card--warn" data-testid="rover-power-evidence">
      <h3>Rover power evidence — {report.status === "blocked" ? "not authorized" : "review required"}</h3>
      <p className="small muted">
        Declared inventory is not a measurement. Motor-driver compilation does not
        verify loaded battery voltage, current limits, logic supply, heating or safe power-on.
      </p>
      <dl>
        <dt>Battery nominal (declared)</dt>
        <dd>{declared.battery_nominal_v ?? "unknown"} V</dd>
        <dt>Battery capacity (declared)</dt>
        <dd>{declared.battery_capacity_mah ?? "unknown"} mAh</dd>
        <dt>Motor count (declared)</dt>
        <dd>{declared.motor_count ?? "unknown"}</dd>
        <dt>Combined declared stall current (not measured)</dt>
        <dd>{declared.simultaneous_stall_current_a ?? "unknown"} A</dd>
        <dt>Physically measured motor rail</dt>
        <dd>{measured.motor_rail_v == null ? "No authenticated measurement" : `${measured.motor_rail_v} V (external review required)`}</dd>
      </dl>
      {blockers.length > 0 && (
        <>
          <h4>Unresolved engineering requirements</h4>
          <ul>
            {blockers.map((item) => (
              <li key={item.code}><strong>{item.code}</strong>: {item.message}</li>
            ))}
          </ul>
        </>
      )}
      {actions.length > 0 && (
        <>
          <h4>Next evidence to collect</h4>
          <ul>{actions.map((action) => <li key={action}>{action}</li>)}</ul>
        </>
      )}
      {report.sources?.l298_datasheet && (
        <p className="small">
          Manufacturer data: <a href={report.sources.l298_datasheet} target="_blank" rel="noreferrer">
            ST L298 datasheet
          </a>. Published voltage-drop tests do not predict this individual rover's readings.
        </p>
      )}
    </section>
  );
}
