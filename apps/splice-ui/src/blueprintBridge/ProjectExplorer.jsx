import { useMemo, useState } from "react";
import { Background, Controls, ReactFlow, ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./ProjectExplorer.css";

const TABS = [
  ["overview", "Overview"], ["parts", "Parts"], ["architecture", "Architecture"],
  ["wiring", "Wiring"], ["mechanical", "Mechanical"], ["code", "Code"],
  ["build", "Build"], ["verify", "Verify"],
];
const LANE = {
  sensor: "Sense", comms: "Sense", mcu: "Compute", module: "Compute",
  actuator: "Act", display: "Act", power: "Power",
};
const NET_COLORS = { data: "#2563eb", power: "#b45309", ground: "#475569" };

function WireGraph({ design }) {
  const graph = useMemo(() => {
    const lanes = { Sense: 0, Compute: 0, Act: 0, Power: 0, Mechanical: 0 };
    const positions = { Sense: 0, Compute: 260, Act: 520, Power: 780, Mechanical: 1040 };
    const nodes = design.parts.map((part) => {
      const lane = LANE[part.category] || "Mechanical";
      const row = lanes[lane]++;
      return {
        id: part.id, position: { x: positions[lane], y: row * 110 },
        data: { label: `${part.name}\n${part.role || part.category}` },
        style: { width: 208, whiteSpace: "pre-line", borderRadius: 8,
          border: "1px solid #94a3b8", padding: 9, fontSize: 12, background: "#fff" },
        draggable: false,
      };
    });
    const edges = design.connections.map((c) => ({
      id: c.id, source: c.from.part, target: c.to.part,
      label: `${c.from.pin} → ${c.to.pin}${c.label ? ` · ${c.label}` : ""}`,
      style: { stroke: NET_COLORS[c.net] || "#475569", strokeWidth: 2 },
      labelStyle: { fontSize: 10 },
      type: "smoothstep",
    }));
    return { nodes, edges };
  }, [design]);
  return (
    <div className="blueprint-explorer__flow" data-testid="blueprint-pin-wiring">
      <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView nodesDraggable={false}
        nodesConnectable={false} elementsSelectable={true} edgesReconnectable={false}
        deleteKeyCode={null} minZoom={0.15} maxZoom={1.5}>
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function AssemblyTree({ roots, parts, depth = 0 }) {
  if (depth > 16) return null;
  return (
    <ul className="blueprint-explorer__tree">
      {roots.map((node, i) => {
        const part = parts.find((p) => p.id === node.part);
        return (
          <li key={`${node.part}-${i}`}>
            <strong>{part?.name || node.part}</strong>
            <span className="muted small"> · schematic placement only</span>
            {node.children?.length > 0 && (
              <AssemblyTree roots={node.children} parts={parts} depth={depth + 1} />
            )}
          </li>
        );
      })}
    </ul>
  );
}

function Verification({ design }) {
  const checks = [
    ["Electrical design", design.evidence.electrical],
    ["KiCad / design checks", design.evidence.design],
    ["Physical measurement", design.evidence.physical],
    ["Fabrication", design.evidence.fabricationAuthorized ? "authorized" : "not_authorized"],
    ["Power-on", design.evidence.powerOnAuthorized ? "reported_authorized" : "not_authorized"],
    ["Release", design.evidence.releaseAuthorized ? "authorized" : "not_authorized"],
  ];
  return (
    <div className="blueprint-explorer__stack" data-testid="blueprint-evidence">
      <p className="blueprint-explorer__warning">
        Viewing a design or importing a package never authorizes fabrication, power-on,
        motor movement or release. Independently check parts, wiring, protection and physical evidence.
      </p>
      <dl className="blueprint-explorer__evidence-grid">
        {checks.map(([name, status]) => (
          <div key={name}>
            <dt>{name}</dt><dd>{String(status).replace(/_/g, " ")}</dd>
          </div>
        ))}
      </dl>
      <p className="muted small">Source: {design.evidence.provenance}</p>
      {design.evidence.revision != null && (
        <p className="muted small">HS revision: {design.evidence.revision}</p>
      )}
    </div>
  );
}

/** Presentation only: OpenBlueprint imports never enter the HS authorization model. */
export default function ProjectExplorer({ design }) {
  const [tab, setTab] = useState("overview");
  const [filter, setFilter] = useState("");
  const filtered = useMemo(() => design.parts.filter((part) =>
    [part.name, part.role, part.category, part.description].some((v) =>
      String(v || "").toLowerCase().includes(filter.toLowerCase())
    )), [design.parts, filter]);
  const total = design.parts.reduce((sum, p) =>
    p.unitCost === null ? sum : sum + p.unitCost * p.qty, 0);
  const unknownCost = design.parts.some((p) => p.unitCost === null);

  return (
    <section className="blueprint-explorer card" data-testid="blueprint-project-explorer">
      <div className="blueprint-explorer__heading">
        <div>
          <p className="eyebrow">Unified project explorer · read-only</p>
          <h2>{design.name}</h2>
          <p className="muted small">{design.source === "openblueprint_import"
            ? "Imported OpenBlueprint proposal · not an HS-verified engineering design"
            : "Hardware Splicer engineering package · reported verification shown separately"}</p>
        </div>
        <span className="blueprint-explorer__status">Physical release not established</span>
      </div>
      <nav className="blueprint-explorer__tabs" aria-label="Project package views">
        {TABS.map(([id, label]) => (
          <button type="button" key={id} className={tab === id ? "active" : ""}
            aria-current={tab === id ? "page" : undefined}
            onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>

      {tab === "overview" && (
        <div className="blueprint-explorer__stack" data-testid="blueprint-overview">
          <p className="lead">{design.summary || "No project summary supplied."}</p>
          <div className="blueprint-explorer__metrics">
            <span><strong>{design.parts.length}</strong> part lines</span>
            <span><strong>{design.connections.length}</strong> pin connections</span>
            <span><strong>{design.instructions.reduce((n, p) => n + p.steps.length, 0)}</strong> steps</span>
          </div>
          <p className="muted small">
            {unknownCost ? "Complete project price unavailable — some part costs are unknown."
              : `Source-estimated part cost: $${total.toFixed(2)} USD (not a live supplier quote).`}
          </p>
          {design.assumptions.length > 0 && (
            <div><h3>Assumptions to check</h3><ul>{design.assumptions.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
          )}
          <Verification design={design} />
        </div>
      )}

      {tab === "parts" && (
        <div data-testid="blueprint-parts">
          <label className="field-label" htmlFor="blueprint-part-filter">Find a part</label>
          <input id="blueprint-part-filter" value={filter}
            onChange={(e) => setFilter(e.target.value)} placeholder="Name, role, category…" />
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Part</th><th>Role / category</th><th>Qty</th><th>Cost</th><th>Evidence</th></tr></thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id}>
                    <td><strong>{p.name}</strong><p className="muted small">{p.description}</p></td>
                    <td>{p.role || p.category}<p className="muted small">{p.source}</p></td>
                    <td>{p.qty}</td>
                    <td>{p.unitCost === null ? "Unknown" : `~$${(p.unitCost * p.qty).toFixed(2)}`}</td>
                    <td>Proposed / unverified</td>
                  </tr>
                ))}
                {filtered.length === 0 && <tr><td colSpan={5}>No matching parts.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "architecture" && (
        <div className="blueprint-explorer__lanes" data-testid="blueprint-architecture">
          {["Sense", "Compute", "Act", "Power", "Mechanical"].map((lane) => {
            const parts = design.parts.filter((p) => (LANE[p.category] || "Mechanical") === lane);
            return (
              <section key={lane}>
                <h3>{lane}</h3>
                {parts.length ? parts.map((p) => (
                  <article key={p.id}><strong>{p.name}</strong><p className="muted small">{p.role || p.category}</p></article>
                )) : <p className="muted small">No identified blocks</p>}
              </section>
            );
          })}
        </div>
      )}

      {tab === "wiring" && (
        <div data-testid="blueprint-wiring">
          {design.connections.length > 0 ? (
            <ReactFlowProvider><WireGraph design={design} /></ReactFlowProvider>
          ) : <p className="blueprint-explorer__warning">
            No source-backed pin-level connection graph is available. Topology is not a wiring schematic.
          </p>}
          {design.topologyOperators.length > 0 && (
            <div><h3>Reported topology operators</h3>
              <ul>{design.topologyOperators.map((op, i) =>
                <li key={op.operator_id || i}><strong>{op.operator_id || op.operator_type}</strong> ·
                  {" "}{(op.inputs || []).join(", ")} → {(op.outputs || []).join(", ")}</li>)}</ul>
            </div>
          )}
          {design.wiringNarrative && (
            <details><summary>HS wiring narrative (not a validated pin graph)</summary>
              <pre className="blueprint-explorer__text">{design.wiringNarrative}</pre>
            </details>
          )}
          {design.connections.length > 0 && <p className="muted small">
            Imported pin relationships are proposals, not independently checked electrical nets.
          </p>}
        </div>
      )}

      {tab === "mechanical" && (
        <div data-testid="blueprint-mechanical">
          <p className="blueprint-explorer__warning">
            {design.source === "openblueprint_import"
              ? "OpenBlueprint's assembly is schematic; dimensions and STL are not verified manufacturing geometry."
              : "HS mechanical source is not automatically a measured fit or fabrication-ready CAD assembly."}
          </p>
          <p className="muted small">Mechanical state: {design.mechanical.status.replace(/_/g, " ")}</p>
          {design.assembly.length > 0
            ? <AssemblyTree roots={design.assembly} parts={design.parts} />
            : <p className="muted">No source-backed assembly hierarchy in this package.</p>}
          <p className="muted small">3D/CAD preview is unavailable in this bridge until an actual model is attached and checked.</p>
        </div>
      )}

      {tab === "code" && (
        <div data-testid="blueprint-code">
          {design.firmware?.source ? (
            <><p className="muted small">Firmware scaffold: {design.firmware.filename || "source"} · not compiled here</p>
              <pre className="blueprint-explorer__text">{design.firmware.source}</pre></>
          ) : <p className="muted">No firmware source is included in this package.</p>}
        </div>
      )}

      {tab === "build" && (
        <div data-testid="blueprint-build">
          <p className="blueprint-explorer__warning">These are proposed instructions. They are not permission to power or fabricate hardware.</p>
          {design.instructions.map((phase) => (
            <section key={phase.id}><h3>{phase.title}</h3>
              <ol>{phase.steps.map((step) => <li key={step.id}>
                <strong>{step.title}</strong> {step.detail}
              </li>)}</ol>
            </section>
          ))}
          {design.instructions.length === 0 && <p className="muted">No build steps supplied.</p>}
        </div>
      )}

      {tab === "verify" && <Verification design={design} />}
    </section>
  );
}
