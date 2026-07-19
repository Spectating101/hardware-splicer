/**
 * Read-only mechatronics surface: firmware + mechanism + authority from package.
 */

function pinEntries(pins) {
  if (!pins || typeof pins !== "object") return [];
  return Object.entries(pins).filter(
    ([k]) => k !== "sourced_from_graph" && k !== "sourced_from_bringup"
  );
}

export default function MechatronicsPanel({ pkg }) {
  const fw = pkg?.firmware_scaffold || pkg?.mechatronics?.firmware_scaffold || null;
  const mech = pkg?.mechanism_pack || pkg?.mechatronics?.mechanism_pack || null;
  const auth =
    pkg?.mechatronics_authority || pkg?.mechatronics?.mechatronics_authority || null;

  const hasAnything = Boolean(fw || mech || auth);
  if (!hasAnything) {
    return (
      <section className="card empty-card" data-testid="mechatronics-panel-empty">
        <h3>Mechatronics</h3>
        <p className="muted small">
          Firmware, mechanism pack, and authority appear after a salvage/mechatronics build.
        </p>
      </section>
    );
  }

  const pins = pinEntries(fw?.pins);
  const outputs = Array.isArray(mech?.outputs) ? mech.outputs : [];
  const level = auth?.current_authority_level || "—";
  const claim =
    auth?.claim_boundary ||
    mech?.claim_boundary ||
    fw?.claim_boundary ||
    "Starter pack — verify on bench.";

  return (
    <section className="card" data-testid="mechatronics-panel">
      <div className="card-header">
        <h3>Mechatronics</h3>
        <span className="chip" data-testid="mechatronics-authority-level">
          {level}
        </span>
      </div>
      <p className="small muted" data-testid="mechatronics-claim">
        {typeof claim === "string" ? claim : JSON.stringify(claim)}
      </p>

      {fw && (
        <div className="mechatronics-block" data-testid="mechatronics-firmware">
          <h4>Firmware</h4>
          <p className="mono small">{fw.filename || "sketch"}</p>
          {pins.length > 0 && (
            <ul className="clean-list small">
              {pins.map(([k, v]) => (
                <li key={k}>
                  <span className="mono">{k}</span> = {String(v)}
                </li>
              ))}
            </ul>
          )}
          {fw.source && (
            <pre className="code-block small" data-testid="mechatronics-firmware-source">
              {String(fw.source).slice(0, 1200)}
              {String(fw.source).length > 1200 ? "\n…" : ""}
            </pre>
          )}
        </div>
      )}

      {mech && (
        <div className="mechatronics-block" data-testid="mechatronics-mechanism">
          <h4>Mechanism</h4>
          <dl className="meta-grid">
            <div>
              <dt>Kind</dt>
              <dd className="mono" data-testid="mechatronics-mech-kind">
                {mech.kind || "—"}
              </dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd data-testid="mechatronics-mech-status">{mech.status || "—"}</dd>
            </div>
          </dl>
          {mech.degraded_reason && (
            <p className="small muted">Degraded: {mech.degraded_reason}</p>
          )}
          {outputs.length > 0 && (
            <ul className="clean-list small">
              {outputs.slice(0, 12).map((o) => (
                <li key={String(o)} className="mono">
                  {String(o)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
