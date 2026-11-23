import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { fetchSceneDecisions, fetchSceneEvidence, fetchSceneFit, fetchSceneKicad, fetchSceneManifest, postSceneDecision } from "../api";
import { BASIS_LABELS, openQuestions } from "../components/fielddeckLogic.js";
import { deviceFindings, evidenceFindings, findTargets, fitFindings, kicadFindings, shortLabel, STATES } from "./deviceFindings.js";
import { EvidenceCanvas } from "./EvidenceCanvas.jsx";
import "./device.css";

// The owner's call on a finding. Recorded next to it; never changes the finding's state.
const DECISIONS = [
  ["ask_agent", "Ask the agent to resolve"],
  ["needs_bench_test", "Needs a bench test"],
  ["accept_risk", "Accept the risk"],
  ["waive", "Waive"],
];
const DECIDABLE = new Set(["open", "unknown", "failing", "clash", "simulated"]);

function DecisionBar({ item, decision, onDecide }) {
  if (!DECIDABLE.has(item.state)) return null;
  const label = (kind) => DECISIONS.find(([id]) => id === kind)?.[1] ?? kind;
  return (
    <div className="dv-decide">
      {decision && <p className="dv-decided">Your call: <strong>{label(decision.decision)}</strong>
        <small> · {decision.at.slice(0, 16).replace("T", " ")} UTC{decision.decision === "ask_agent" ? " · queued for the agent" : ""}</small></p>}
      <div className="dv-decide-row" role="group" aria-label="Your call on this finding">
        {DECISIONS.map(([id, text]) => (
          <button key={id} type="button" aria-pressed={decision?.decision === id} onClick={() => onDecide(item.id, id)}>{text}</button>
        ))}
      </div>
    </div>
  );
}

const FieldDeckScene = lazy(() => import("../components/FieldDeckScene.jsx"));

const OVERVIEW = { selected: null, explode: 0.6, faceView: false };

// The same numbers the amber pins carry on the model.
function PinNumbers({ numbers }) {
  if (!numbers?.length) return null;
  return <span className="dv-pins" aria-label={`Marked on the model as ${numbers.join(", ")}`}>
    {numbers.map((number) => <span key={number} className="dv-pin" aria-hidden="true">{number}</span>)}
  </span>;
}

function StateWord({ state }) {
  return <span className="dv-state" data-state={state}>{STATES[state] ?? state}</span>;
}

function Source({ basis }) {
  if (!basis) return null;
  return /^https?:\/\//.test(basis)
    ? <a href={basis} target="_blank" rel="noreferrer">{new URL(basis).hostname}</a>
    : <span>{basis}</span>;
}

function SelectionCard({ row, index, sidecars, findings, onShow, onSelect }) {
  if (!row) return null;
  const scene = sidecars?.[row.revision];
  // One link per question: the same question can be raised by more than one record.
  const related = findings.filter((item, index, all) => item.view.selected === row.key
    && all.findIndex((other) => other.view.selected === row.key && other.question === item.question) === index);
  if (row.link) {
    const { link } = row;
    const end = (id) => index.byPart.get(`${row.revision}:${id}`);
    return (
      <aside className="dv-card" aria-label="Selected connection" data-stage-edge="right">
        <p className="dv-card-kind">Connection</p>
        <h2>{link.label}</h2>
        <p className="dv-ends">
          {[link.from_part_id, link.to_part_id].map((id, i) => (
            <span key={id}>{i ? " → " : ""}<button type="button" className="dv-link" onClick={() => onSelect(end(id)?.key)}>
              {shortLabel(end(id)?.part.label ?? id)}</button></span>
          ))}
        </p>
        <dl className="dv-facts">
          <div><dt>Ends in model</dt><dd>{link.endpoints_present ? "both" : "not both"}</dd></div>
          <div><dt>Open checks</dt><dd>{link.open_checks.length || "none recorded"}</dd></div>
          <div><dt>Hardware</dt><dd>not tested</dd></div>
        </dl>
        {link.open_checks.length > 0 && <ul className="dv-checks">{link.open_checks.map((check) => <li key={check}>{check.replace(/_/g, " ")}</li>)}</ul>}
        {link.source && <p className="dv-source">Source · <Source basis={link.source} /></p>}
      </aside>
    );
  }
  const { part } = row;
  const links = (scene?.interfaces ?? []).filter((link) => [link.from_part_id, link.to_part_id].includes(part.part_id));
  const evidence = (part.evidence ?? []).filter((record) => record.field !== "mesh_bounds_mm");
  return (
    <aside className="dv-card" aria-label="Selected part" data-stage-edge="right">
      <p className="dv-card-kind">Part{row.delta && row.delta !== "unchanged" ? ` · ${row.delta}` : ""}</p>
      <h2>{shortLabel(part.label)}</h2>
      {part.label !== shortLabel(part.label) && <p className="dv-full-label">{part.label}</p>}
      <dl className="dv-facts">
        <div><dt>Shape from</dt><dd>{BASIS_LABELS[part.geometry_basis] ?? "Unknown"}</dd></div>
        <div><dt>BOM line</dt><dd>{part.bom_line ?? "not on the BOM"}</dd></div>
        <div><dt>Hardware</dt><dd>not tested</dd></div>
      </dl>
      {evidence.length > 0 && <table className="dv-evidence">
        <thead><tr><th scope="col">Record</th><th scope="col">Value</th><th scope="col">Basis</th></tr></thead>
        <tbody>{evidence.slice(0, 8).map((record, i) => (
          <tr key={`${record.field}-${i}`}>
            <th scope="row">{record.field.replace(/_/g, " ")}</th>
            <td className="dv-num">{record.value == null ? "—" : Array.isArray(record.value) ? record.value.join(" × ") : String(record.value)}</td>
            <td>{record.state}</td>
          </tr>
        ))}</tbody>
      </table>}
      {links.length > 0 && <div className="dv-related">
        <h3>Connections</h3>
        {links.map((link) => (
          <button key={link.interface_id} type="button" className="dv-link" onClick={() => onSelect(`${row.revision}:link:${link.interface_id}`)}>
            {link.label}{link.open_checks.length ? ` · ${link.open_checks.length} open` : ""}
          </button>
        ))}
      </div>}
      {related.length > 0 && <div className="dv-related">
        <h3>Questions about it</h3>
        {related.map((item) => <button key={item.id} type="button" className="dv-link" onClick={() => onShow(item)}>{item.question}</button>)}
      </div>}
    </aside>
  );
}

export default function DeviceWorkspace({ sceneId, onExit }) {
  const [manifest, setManifest] = useState(null);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [command, setCommand] = useState(null);
  const [active, setActive] = useState(null);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState("");
  const [fit, setFit] = useState({ state: "idle", report: null, error: "" });
  const [evidence, setEvidence] = useState(null);
  const [kicad, setKicad] = useState({ state: "idle", report: null, error: "" });
  const [decisions, setDecisions] = useState({});
  const [canvasHidden, setCanvasHidden] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setDecisions({});
    fetchSceneDecisions(sceneId, controller.signal)
      .then((rows) => { if (!controller.signal.aborted) setDecisions(rows); })
      .catch(() => {});
    return () => controller.abort();
  }, [sceneId]);

  async function decide(findingId, kind) {
    try {
      const row = await postSceneDecision(sceneId, findingId, kind);
      setDecisions((current) => ({ ...current, [findingId]: row }));
    } catch {
      setDecisions((current) => current);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null); setError("");
    fetchSceneManifest(sceneId, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setManifest(body); })
      .catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [sceneId]);

  const labelOf = (rev) => data?.revisions?.find(([id]) => id === rev)?.[1] ?? rev;
  const drawable = manifest?.geometry_status === "available";
  const fitRevision = data?.compare?.target ?? data?.revisions?.at(-1)?.[0] ?? null;
  const shownRevision = fitRevision ?? manifest?.compare?.target ?? manifest?.revisions?.at(-1)?.id ?? null;
  const boardRevision = manifest?.revisions?.find((row) => row.id === shownRevision && row.board) ? shownRevision : null;
  useEffect(() => {
    const controller = new AbortController();
    setEvidence(null);
    fetchSceneEvidence(sceneId, controller.signal)
      .then((body) => { if (!controller.signal.aborted) setEvidence(body.records); })
      .catch(() => { if (!controller.signal.aborted) setEvidence([]); });
    return () => controller.abort();
  }, [sceneId]);
  // KiCad's own DRC/ERC, for a revision that names its board files.
  useEffect(() => {
    if (!boardRevision) return undefined;
    const controller = new AbortController();
    setKicad({ state: "loading", report: null, error: "" });
    fetchSceneKicad(sceneId, boardRevision, controller.signal)
      .then((report) => { if (!controller.signal.aborted) setKicad({ state: "ready", report, error: "" }); })
      .catch((cause) => { if (!controller.signal.aborted) setKicad({ state: "error", report: null, error: cause.message }); });
    return () => controller.abort();
  }, [sceneId, boardRevision]);
  // The model as measured by the server's fit engine: computed once per model, then cached there.
  useEffect(() => {
    if (!fitRevision) return undefined;
    const controller = new AbortController();
    setFit({ state: "loading", report: null, error: "" });
    fetchSceneFit(sceneId, fitRevision, controller.signal)
      .then((report) => { if (!controller.signal.aborted) setFit({ state: "ready", report, error: "" }); })
      .catch((cause) => { if (!controller.signal.aborted) setFit({ state: "error", report: null, error: cause.message }); });
    return () => controller.abort();
  }, [sceneId, fitRevision]);
  const findings = useMemo(() => {
    const recorded = data?.sidecars ? deviceFindings({
      sidecars: data.sidecars, compare: data.compare, focusPart: data.focusPart, faceFit: data.faceFit, labelOf,
    }) : [];
    const measured = data?.sidecars ? fitFindings(fit.report, { sidecar: data.sidecars[fitRevision], revision: fitRevision, labelOf }) : [];
    const partIds = new Set((data?.sidecars?.[fitRevision]?.parts ?? []).map((part) => part.part_id));
    const records = evidenceFindings(evidence, { revision: shownRevision, partIds });
    const checks = kicadFindings(kicad.report, { revision: shownRevision });
    // One "What was chosen" group: the scene's own records first, then any strategy record.
    const chosen = [...recorded, ...records].filter((group) => group.id === "chosen");
    const chosenGroup = chosen.length ? [{ id: "chosen", title: "What was chosen", items: chosen.flatMap((group) => group.items) }] : [];
    const rest = (groups) => groups.filter((group) => group.id !== "chosen");
    return [...chosenGroup, ...checks, ...measured, ...rest(records), ...rest(recorded)];
  }, [data?.sidecars, data?.compare, data?.focusPart, data?.faceFit, data?.revisions, fit.report, fitRevision, evidence, kicad.report, shownRevision]);
  // The stage numbers open questions in this order; a finding shows the numbers of its own reasons.
  const pinNumbers = useMemo(() => {
    if (!data?.sidecars || !data?.index) return new Map();
    const order = data.compare ? [data.compare.target, data.compare.base] : Object.keys(data.sidecars);
    const byReason = new Map();
    for (const { reason, number } of openQuestions(data.sidecars, data.index, order)) {
      if (!byReason.has(reason)) byReason.set(reason, number);
    }
    return byReason;
  }, [data?.sidecars, data?.index, data?.compare]);
  const numbersFor = (item) => [...new Set((item.reasons ?? []).map((reason) => pinNumbers.get(reason)).filter(Boolean))];
  const items = findings.flatMap((group) => group.items);
  const activeItem = items.find((item) => item.id === active) ?? null;
  const target = data?.compare?.target ?? data?.revisions?.at(-1)?.[0];
  const matches = data?.index && target ? findTargets(data.index, target, query) : [];
  const selectedRow = data?.index?.byKey.get(selected) ?? null;
  const openCount = items.filter((item) => item.state === "open" || item.state === "unknown").length;
  const failingCount = items.filter((item) => item.state === "failing" || item.state === "clash").length;
  // Search hint from this device's own parts, not a fixed example.
  const hint = useMemo(() => {
    const parts = Object.values(data?.sidecars ?? {})[0]?.parts ?? [];
    const names = parts.filter((part) => part.geometry_basis !== "copper" && part.part_id !== "world")
      .map((part) => String(part.label ?? part.part_id).split(" · ")[0]).filter((name) => name.length <= 14);
    return names.length ? `${names.slice(0, 3).join(", ")}…` : "a part or reference…";
  }, [data]);
  const recipe = activeItem?.view ? [
    activeItem.view.mode === "compare" ? "comparing revisions" : `revision ${labelOf(activeItem.view.mode)}`,
    activeItem.view.faceView ? "face view" : null,
    activeItem.view.selected ? `${1 + (activeItem.view.also?.length ?? 0)} highlighted` : "whole device",
    activeItem.view.explode ? "exploded" : null,
  ].filter(Boolean).join(" · ") : "";

  function show(item) {
    setActive(item.id);
    setCanvasHidden(false);
    setCommand({ ...item.view });
  }
  function select(key) {
    if (!key) return;
    setActive(null);
    setCommand({ mode: target, selected: key, explode: 0.45, faceView: false });
  }
  function overview() {
    setActive(null);
    setCommand({ ...OVERVIEW, mode: data?.compare ? "compare" : target });
  }

  return (
    <div className="dv" data-testid="device-workspace">
      <div className="dv-stage">
        {manifest && !drawable && <p className="dv-loading dv-no-model">
          No 3D model for this project{manifest.geometry_note ? `: ${manifest.geometry_note.split("\n")[0].replace(/_/g, " ")}.` : "."}
          {manifest.geometry_note?.includes("\n") && <><br />{manifest.geometry_note.split("\n").slice(1).join(" ")}</>}
        </p>}
        {manifest && drawable && <Suspense fallback={<p className="dv-loading">Loading the 3D device…</p>}>
          <FieldDeckScene projectId={sceneId} manifest={manifest} chrome="none" command={command}
            onSelectionChange={setSelected} onReady={setData} />
        </Suspense>}
        {error && <p className="dv-loading" role="alert">Device model unavailable: {error}</p>}
      </div>

      <header className="dv-head" data-stage-edge="top">
        {onExit && <button type="button" className="dv-back" onClick={onExit} aria-label="Back">←</button>}
        <div>
          <h1>{manifest?.title ?? "Device"}</h1>
          <p>{manifest?.subtitle}{data?.compare ? ` · compared with the ${labelOf(data.compare.base)} revision` : ""}</p>
        </div>
        <p className="dv-truth">Physical fit <strong>not tested on hardware</strong> {failingCount > 0 && <> · <strong className="dv-failing">{failingCount} failing {failingCount === 1 ? "check" : "checks"}</strong></>} · {openCount} open or unknown</p>
      </header>

      <section className="dv-questions" aria-label="Questions about this device" data-stage-edge="left">
        <label className="dv-find">
          <span>Find a part or connection</span>
          <input type="search" value={query} placeholder={hint} onChange={(event) => setQuery(event.target.value)} />
        </label>
        {query && <ul className="dv-matches" aria-label="Matches">
          {matches.length ? matches.map((match) => (
            <li key={match.key}><button type="button" onClick={() => { select(match.key); setQuery(""); }}>
              {match.label}<small>{match.kind}</small></button></li>
          )) : <li className="dv-none">No part or connection matches “{query}”.</li>}
        </ul>}
        {drawable && !data?.sidecars && !error && <p className="dv-none">Reading the device records…</p>}
        {kicad.state === "loading" && <p className="dv-none" role="status">Running KiCad's DRC and ERC on the board files…</p>}
        {kicad.state === "error" && <p className="dv-none" role="status">KiCad checks unavailable: {kicad.error}</p>}
        {fit.state === "loading" && <p className="dv-none" role="status">Measuring the CAD model: part-to-part clearances and collisions. The first measurement of a model takes a few seconds.</p>}
        {fit.state === "error" && <p className="dv-none" role="status">Measured fit unavailable: {fit.error}</p>}
        {findings.map((group) => (
          <div key={group.id} className="dv-group">
            <h2>{group.title}</h2>
            <ol>
              {group.items.map((item) => (
                <li key={item.id} data-active={item.id === active}>
                  <button type="button" className="dv-question" aria-pressed={item.id === active} onClick={() => show(item)}>
                    <span className="dv-q"><PinNumbers numbers={numbersFor(item)} />{item.question}</span>
                    <span className="dv-a">{item.answer}</span>
                    <StateWord state={item.state} />
                  </button>
                  {item.id === active && (item.detail?.length > 0 || item.basis || item.next) && <div className="dv-detail">
                    {item.next && <p className="dv-next"><span>Next</span> {item.next}</p>}
                    {item.detail?.length > 0 && <ul>{item.detail.map((line) => <li key={line}>{line}</li>)}</ul>}
                    {item.basis && <p>Basis · <Source basis={item.basis} /></p>}
                    <DecisionBar item={item} decision={decisions[item.id]} onDecide={decide} />
                  </div>}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </section>

      {activeItem && <div className="dv-lens" role="status" data-stage-edge="top">
        <span>Showing</span> <strong>{activeItem.question}</strong>
        {recipe && <small className="dv-recipe">{recipe}</small>}
        <button type="button" onClick={overview}>Back to whole device</button>
      </div>}

      {activeItem?.canvas && !canvasHidden && <div className="dv-canvas-host" data-wide={!drawable || undefined}>
        <EvidenceCanvas canvas={activeItem.canvas} onClose={() => setCanvasHidden(true)} />
      </div>}

      {!activeItem?.view.faceView && !(activeItem?.canvas && !canvasHidden) && <SelectionCard row={selectedRow} index={data?.index} sidecars={data?.sidecars} findings={items}
        onShow={show} onSelect={select} />}
    </div>
  );
}
