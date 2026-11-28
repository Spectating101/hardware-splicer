import { useState } from "react";
import { Icon, Outcome } from "./icons.jsx";
import { OUTCOME_LABEL, toolTitle } from "./catalog.js";
import { renderUrl } from "./benchApi.js";

/** The pipeline every HS board goes through, with one recorded run laid over it. */
export function SpineView({ spine, selectedKey, onSelectStep, onShowRun }) {
  if (!spine) return <ViewEmpty text="Loading the spine…" />;
  const { steps, run } = spine;
  const present = new Set(steps.map((s) => s.run.outcome));
  return (
    <div className="wb-spine">
      <header className="wb-runbar">
        <h2>{run ? <button type="button" className="wb-title-link" onClick={onShowRun} title="Run details">{run.name}</button> : "No recorded run"}</h2>
        <Legend outcomes={OUTCOME_ORDER.filter((o) => present.has(o))} />
      </header>
      <ol className="wb-steps" aria-label="Board pipeline steps">
        {steps.map((s) => (
          <li key={s.key} className={`wb-station${s.gate ? " is-gate" : ""}${selectedKey === s.key ? " is-selected" : ""} out-${s.run.outcome}`}>
            <button type="button" className="wb-step" onClick={() => onSelectStep(s.key)} aria-pressed={selectedKey === s.key}
              aria-label={`${s.n} ${s.title}${s.gate ? ", gate" : ""}: ${OUTCOME_LABEL[s.run.outcome]}, ${s.run.line}`}>
              <span className="wb-step-head" aria-hidden="true">
                <span className="wb-step-n mono">{String(s.n).padStart(2, "0")}</span>
                <Outcome outcome={s.run.outcome} />
              </span>
              <span className="wb-step-title" aria-hidden="true">{s.title}</span>
              <span className="wb-step-line" aria-hidden="true">{s.run.line}</span>
            </button>
          </li>
        ))}
      </ol>
      {run?.not_checked?.length > 0 && (
        <section className="wb-spine-notes">
          <h3>Not checked on this run</h3>
          <ul className="wb-notchecked">{run.not_checked.map((t) => <li key={t}>{t}</li>)}</ul>
        </section>
      )}
    </div>
  );
}

function pluginLink(name, names, onSelect, label) {
  if (!names?.has(name)) return label ?? name;
  return <button type="button" className="wb-inline-link" onClick={() => onSelect(name)}>{label ?? name}</button>;
}

const OUTCOME_ORDER = ["clean", "failed", "recorded", "not_run", "unknown"];

export function listWords(ns = []) {
  if (ns.length < 2) return ns.join("");
  return `${ns.slice(0, -1).join(", ")} and ${ns[ns.length - 1]}`;
}

function Legend({ outcomes }) {
  return (
    <ul className="wb-legend" aria-label="Legend">
      <li><span className="wb-legend-gate" aria-hidden="true" /> gate</li>
      {outcomes.map((o) => (
        <li key={o}><Outcome outcome={o} /> {OUTCOME_LABEL[o]}</li>
      ))}
    </ul>
  );
}

export function BoardView({ spine }) {
  const renders = spine?.run?.renders ?? [];
  const [which, setWhich] = useState(null);
  const current = which ?? renders[0];
  if (!spine) return <ViewEmpty text="Loading…" />;
  if (!current) return <ViewEmpty text="No render recorded for this run." />;
  return (
    <div className="wb-board">
      <div className="wb-subtabs" role="tablist" aria-label="Render">
        {renders.map((r) => (
          <button key={r} type="button" role="tab" aria-selected={r === current} className={r === current ? "is-active" : ""} onClick={() => setWhich(r)}>
            {r === "top" ? "Top" : r === "iso" ? "Isometric" : r}
          </button>
        ))}
        <span className="wb-subtabs-note">KiCad render of the routed board · {spine.run.name}</span>
      </div>
      <div className="wb-board-stage">
        <img src={renderUrl(current)} alt={`${spine.run.name}, ${current === "top" ? "top" : "isometric"} render`} />
      </div>
    </div>
  );
}

export function MeasuresView({ measures, onSelectPlugin, pluginNames }) {
  if (!measures) return <ViewEmpty text="Loading the measured records…" />;
  const { checkers, routers, predictions } = measures;
  return (
    <div className="wb-measures">
      {checkers && (
        <section className="wb-measure">
          <header>
            <h2>Schematic checkers on held-out bugs</h2>
            <span className="mono wb-record">{checkers.record}</span>
          </header>
          <p className="wb-question">{checkers.question}: {checkers.cases} cases, captured {checkers.captured}.</p>
          <table className="wb-table wb-bars">
            <thead><tr><th scope="col">Checker</th><th scope="col" className="num">Caught</th><th scope="col"><span className="sr-only">Share</span></th></tr></thead>
            <tbody>
              {checkers.rows.map((r) => (
                <tr key={r.name} className={r.name.startsWith("HS") ? "is-hs" : r.name.startsWith("All") ? "is-all" : ""}>
                  <th scope="row">{pluginNames?.has(r.name) || r.name === "KiCad ERC" ? pluginLink(r.name === "KiCad ERC" ? "KiCad ERC and DRC (kicad-cli)" : r.name, pluginNames, onSelectPlugin, r.name) : r.name}</th>
                  <td className="num mono">{r.caught} / {checkers.cases}</td>
                  <td className="bar"><span style={{ width: `${(100 * (r.caught ?? 0)) / (checkers.cases || 1)}%` }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="wb-says">{checkers.says}</p>
        </section>
      )}
      {routers && (
        <section className="wb-measure">
          <header>
            <h2>Routers on designers' boards</h2>
            <span className="mono wb-record">{routers.record}</span>
          </header>
          <p className="wb-question">{routers.question}</p>
          <div className="wb-table-scroll">
            <table className="wb-table">
              <thead>
                <tr><th scope="col" rowSpan={2}>Board</th><th scope="colgroup" colSpan={3}>KiCadRoutingTools</th><th scope="colgroup" colSpan={3}>Copper</th><th scope="colgroup" colSpan={2}>Designer</th></tr>
                <tr>{["DRC err", "open", "vias", "DRC err", "open", "vias", "vias", "track mm"].map((h, i) => <th scope="col" className="num" key={i}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {routers.rows.map((r) => (
                  <tr key={r.board}>
                    <th scope="row" className="mono">{r.board}</th>
                    <Cells v={r.krt} keys={["drc_errors", "unconnected", "vias"]} />
                    <Cells v={r.copper} keys={["drc_errors", ["unconnected", "unrouted"], "vias"]} />
                    <Cells v={r.designer} keys={["vias", "track_length_mm"]} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="wb-says">{routers.says}</p>
          {routers.limits && <p className="wb-boundary">{routers.limits}</p>}
        </section>
      )}
      {predictions && (
        <section className="wb-measure">
          <header>
            <h2>Prediction ledger</h2>
            <span className="mono wb-record">{predictions.record}</span>
          </header>
          <p className="wb-question">{predictions.rule}</p>
          <table className="wb-table">
            <thead><tr><th scope="col">Id</th><th scope="col">Design</th><th scope="col">Quantity</th><th scope="col">Status</th></tr></thead>
            <tbody>
              {predictions.rows.map((p) => (
                <tr key={p.id}><td className="mono">{p.id}</td><td>{p.design}</td><td>{p.quantity}</td><td className="mono">{p.status}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

function Cells({ v, keys }) {
  return keys.map((k) => {
    const names = Array.isArray(k) ? k : [k];
    const val = v ? names.map((n) => v[n]).find((x) => x !== undefined) : undefined;
    const shown = val === undefined || val === null ? "—" : String(val);
    const bad = names[0] === "drc_errors" || names[0] === "unconnected" ? Number(val) > 0 : false;
    return <td key={names[0]} className={`num mono${bad ? " is-bad" : ""}`}>{shown}</td>;
  });
}

export function ResultView({ run, tools }) {
  if (!run) {
    return (
      <ViewEmpty text="Nothing run yet. Pick a tool in the explorer, fill its inputs in the Inspector and press Run (Ctrl Enter)." />
    );
  }
  const env = run.env;
  return (
    <div className="wb-result">
      <header className="wb-runbar">
        <div className="wb-runbar-main">
          <h2>{toolTitle(run.tool)} <span className="mono wb-dim">{run.tool}</span></h2>
          <span className={`wb-status is-${run.status}`}>{STATUS[run.status]}</span>
          {run.ms !== null && <span className="wb-runbar-meta mono">{fmtMs(run.ms)}</span>}
        </div>
      </header>
      {run.status === "running" && <p className="wb-muted">Running on the HS engine…</p>}
      {run.status === "error" && <p className="wb-error-text">{run.error}</p>}
      {env && (
        <>
          {env.summary && <p className="wb-summary">{typeof env.summary === "string" ? env.summary : <JsonTree value={env.summary} open />}</p>}
          {env.problems?.length > 0 && (
            <section className="wb-block">
              <h3>Problems <span className="wb-count">{env.problems.length}</span></h3>
              <ul className="wb-problems">{env.problems.map((p, i) => <li key={i}>{typeof p === "string" ? p : JSON.stringify(p)}</li>)}</ul>
            </section>
          )}
          {env.claim_boundary && (
            <section className="wb-block">
              <h3>What this does not show</h3>
              <p className="wb-boundary">{typeof env.claim_boundary === "string" ? env.claim_boundary : JSON.stringify(env.claim_boundary)}</p>
            </section>
          )}
          {env.sources?.length > 0 && (
            <section className="wb-block">
              <h3>Sources <span className="wb-count">{env.sources.length}</span></h3>
              <ul className="wb-sources">{env.sources.map((s, i) => <li key={i}><SourceLine s={s} /></li>)}</ul>
            </section>
          )}
          {tablesOf(env.result).map(([key, rows, cols]) => (
            <section className="wb-block" key={key}>
              <h3>{key} <span className="wb-count">{rows.length}</span></h3>
              <div className="wb-table-scroll">
                <table className="wb-table">
                  <thead><tr>{cols.map((c) => <th scope="col" key={c} className={rows.every((r) => typeof r[c] !== "string") && rows.some((r) => typeof r[c] === "number") ? "num" : ""}>{c}</th>)}</tr></thead>
                  <tbody>
                    {rows.slice(0, 60).map((r, i) => (
                      <tr key={i}>{cols.map((c) => <td key={c} className={rows.every((x) => typeof x[c] !== "string") && rows.some((x) => typeof x[c] === "number") ? "num mono" : ""}>{cell(r[c])}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > 60 && <p className="wb-muted">First 60 of {rows.length}; all of them are in the raw result below.</p>}
            </section>
          ))}
          <details className="wb-raw">
            <summary>Raw result and arguments</summary>
            <div className="wb-tree mono"><JsonTree value={env.result} open depth={0} /></div>
            <pre className="wb-args mono">{JSON.stringify(run.args, null, 2)}</pre>
          </details>
        </>
      )}
    </div>
  );
}

/** Top-level lists of flat records in a result, shown as tables: [key, rows, columns]. */
export function tablesOf(result) {
  if (!result || typeof result !== "object" || Array.isArray(result)) return [];
  const flat = (v) => v === null || ["string", "number", "boolean"].includes(typeof v);
  return Object.entries(result).flatMap(([key, v]) => {
    if (!Array.isArray(v) || !v.length || !v.every((r) => r && typeof r === "object" && !Array.isArray(r))) return [];
    const cols = [...new Set(v.flatMap((r) => Object.keys(r).filter((k) => flat(r[k]))))].slice(0, 8);
    return cols.length >= 2 ? [[key, v, cols]] : [];
  });
}

function cell(v) {
  if (v === undefined || v === null) return "—";
  return String(v);
}

const STATUS = { running: "running", ok: "ok", problems: "problems reported", error: "request failed" };

export function fmtMs(ms) {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function SourceLine({ s }) {
  const text = typeof s === "string" ? s : s?.url ?? s?.title ?? JSON.stringify(s);
  const url = typeof s === "string" ? (s.match(/https?:\/\/\S+/)?.[0] ?? null) : s?.url ?? null;
  if (!url) return text;
  return <a href={url} target="_blank" rel="noreferrer">{text} <Icon name="external" size={12} /></a>;
}

/** Collapsible JSON: objects and arrays fold; long arrays show their length before opening. */
export function JsonTree({ value, open = false, depth = 0, name }) {
  const [isOpen, setOpen] = useState(open || depth < 1);
  const label = name !== undefined ? <span className="jt-key">{name}</span> : null;
  if (value === null || typeof value !== "object") {
    const cls = value === null ? "jt-null" : typeof value === "number" ? "jt-num" : typeof value === "boolean" ? "jt-bool" : "jt-str";
    return <div className="jt-row">{label}{label && <span className="jt-colon">: </span>}<span className={cls}>{value === null ? "null" : typeof value === "string" ? value : String(value)}</span></div>;
  }
  const entries = Array.isArray(value) ? value.map((v, i) => [i, v]) : Object.entries(value);
  const brief = Array.isArray(value) ? `[${entries.length}]` : `{${entries.length}}`;
  return (
    <div className="jt-node">
      <button type="button" className="jt-toggle" aria-expanded={isOpen} onClick={() => setOpen((v) => !v)}>
        <Icon name="chevron" size={12} className={isOpen ? "is-open" : ""} />
        {label}{label && <span className="jt-colon">: </span>}<span className="jt-brief">{brief}</span>
      </button>
      {isOpen && <div className="jt-children">{entries.map(([k, v]) => <JsonTree key={k} name={k} value={v} depth={depth + 1} />)}</div>}
    </div>
  );
}

function ViewEmpty({ text }) {
  return <div className="wb-viewempty"><p>{text}</p></div>;
}
