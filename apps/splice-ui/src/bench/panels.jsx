import { useEffect, useMemo, useRef, useState } from "react";
import { Icon, Outcome } from "./icons.jsx";
import { EXAMPLES, OUTCOME_LABEL, ROLE_LABELS, TOOL_GROUPS, groupOf, toolTitle } from "./catalog.js";
import { SchemaForm } from "./SchemaForm.jsx";
import { fmtMs, listWords } from "./views.jsx";

/**
 * Palette ranking: the name before its hint; a whole substring first, then the name's initials
 * ("krt" -> KiCadRoutingTools), then the letters merely in order.
 */
export function score(q, label, hint) {
  const one = (raw, weight) => {
    if (!raw) return 0;
    const t = String(raw).toLowerCase();
    const at = t.indexOf(q);
    if (at >= 0) return weight * (100 - Math.min(at, 50));
    const initials = String(raw).split(/[\s_\-/().·]+|(?=[A-Z][a-z])/).filter(Boolean).map((w) => w[0].toLowerCase()).join("");
    if (inOrder(q, initials)) return weight * 40;
    return inOrder(q, t) ? weight * 5 : 0;
  };
  return Math.max(one(label, 2), one(hint, 1));
}

function inOrder(q, t) {
  let i = 0;
  for (const ch of t) if (ch === q[i]) i += 1;
  return i === q.length;
}

const matches = (q, ...texts) => !q || texts.some((t) => t && String(t).toLowerCase().includes(q));

/* ---------------------------------------------------------------- Explorer */

export function Explorer({ tools, plugins, selection, onSelect, engine }) {
  const [q, setQ] = useState("");
  const [toggled, setToggled] = useState(() => new Set());
  const query = q.trim().toLowerCase();
  const toggle = (key) => setToggled((s) => { const n = new Set(s); if (n.has(key)) n.delete(key); else n.add(key); return n; });

  const toolGroups = useMemo(() => {
    const by = new Map(TOOL_GROUPS.map(([g]) => [g, []]));
    for (const t of tools ?? []) {
      if (!matches(query, t.name, toolTitle(t.name), t.description)) continue;
      const g = groupOf(t.name);
      if (!by.has(g)) by.set(g, []);
      by.get(g).push(t);
    }
    return [...by.entries()].filter(([, list]) => list.length);
  }, [tools, query]);
  const pluginGroups = useMemo(() => {
    const by = new Map();
    for (const p of plugins ?? []) {
      if (!matches(query, p.name, p.role, p.licence, p.measured)) continue;
      if (!by.has(p.role)) by.set(p.role, []);
      by.get(p.role).push(p);
    }
    return [...by.entries()];
  }, [plugins, query]);

  // Sections start open and groups start closed; a filter opens everything, and the selection's group opens itself.
  const selectedGroup = selection?.kind === "tool" ? `tg-${groupOf(selection.id)}`
    : selection?.kind === "plugin" ? `pg-${(plugins ?? []).find((p) => p.name === selection.id)?.role}` : null;
  const sectionOpen = (key) => query !== "" || !toggled.has(key);
  const groupOpen = (key) => query !== "" || toggled.has(key) !== (key === selectedGroup);

  const sel = (kind, id) => selection?.kind === kind && selection?.id === id;
  const nothing = query && !toolGroups.length && !pluginGroups.length;

  return (
    <nav className="wb-explorer" aria-label="Explorer">
      <div className="wb-search">
        <Icon name="search" size={14} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter tools"
          aria-label="Filter tools" spellCheck={false} />
      </div>
      <div className="wb-tree-scroll">
        {engine === "offline" && (
          <p className="wb-explorer-note">The HS engine is not answering. Start it with <code>hs-serve</code>, then reload.</p>
        )}
        <TreeSection id="tools" label="HS tools" meta={tools ? String(tools.length) : null} open={sectionOpen("tools")} onToggle={toggle}>
          {toolGroups.map(([group, list]) => (
            <TreeSection key={group} id={`tg-${group}`} label={group} meta={String(list.length)} nested open={groupOpen(`tg-${group}`)} onToggle={toggle}>
              {list.map((t) => (
                <TreeRow key={t.name} selected={sel("tool", t.name)} onClick={() => onSelect({ kind: "tool", id: t.name })}
                  label={toolTitle(t.name)} title={t.name} />
              ))}
            </TreeSection>
          ))}
        </TreeSection>
        <TreeSection id="plugins" label="Outside tools" meta={plugins ? String(plugins.length) : null} open={sectionOpen("plugins")} onToggle={toggle}>
          {pluginGroups.map(([role, list]) => (
            <TreeSection key={role} id={`pg-${role}`} label={ROLE_LABELS[role] ?? role} meta={String(list.length)} nested open={groupOpen(`pg-${role}`)} onToggle={toggle}>
              {list.map((p) => (
                <TreeRow key={p.name} selected={sel("plugin", p.name)} onClick={() => onSelect({ kind: "plugin", id: p.name })}
                  label={p.name} title={`${p.name} · ${p.status} · ${p.licence}`} dim={p.status !== "integrated"} />
              ))}
            </TreeSection>
          ))}
        </TreeSection>
        {nothing && <p className="wb-explorer-note">Nothing matches “{q}”.</p>}
      </div>
    </nav>
  );
}

function TreeSection({ id, icon, label, meta, open, onToggle, nested, children }) {
  return (
    <div className={`wb-section${nested ? " is-nested" : ""}`}>
      <button type="button" className="wb-section-head" aria-expanded={open} onClick={() => onToggle(id)}>
        <Icon name="chevron" size={12} className={open ? "is-open" : ""} />
        {icon && <Icon name={icon} size={14} />}
        <span className="wb-section-label">{label}</span>
        {meta && <span className="wb-section-meta">{meta}</span>}
      </button>
      {open && <div className="wb-section-body" role="list">{children}</div>}
    </div>
  );
}

function TreeRow({ selected, onClick, lead, label, sub, trail, title, dim }) {
  return (
    <button type="button" role="listitem" className={`wb-row${selected ? " is-selected" : ""}${dim ? " is-dim" : ""}`} onClick={onClick} title={title}
      aria-current={selected ? "true" : undefined}>
      {lead}
      <span className="wb-row-label">{label}</span>
      {sub && <span className="wb-row-sub">{sub}</span>}
      {trail}
    </button>
  );
}

/* ---------------------------------------------------------------- Inspector */

export function Inspector(props) {
  const { selection } = props;
  if (!selection) return <RunInspector {...props} />;
  if (selection.kind === "step") return <StepInspector {...props} />;
  if (selection.kind === "tool") return <ToolInspector {...props} />;
  return <PluginInspector {...props} />;
}

function InspectorShell({ kind, title, sub, children, footer }) {
  return (
    <aside className="wb-inspector" aria-label="Inspector">
      <header className="wb-insp-head">
        <h2>{title}</h2>
        {(sub || kind) && (
          <p className="wb-insp-sub">
            {sub && <span className="mono">{sub}</span>}
            {sub && kind && <span aria-hidden="true"> · </span>}
            {kind && <span>{kind}</span>}
          </p>
        )}
      </header>
      <div className="wb-insp-body">{children}</div>
      {footer && <footer className="wb-insp-foot">{footer}</footer>}
    </aside>
  );
}

function Prop({ label, children, mono }) {
  return (
    <div className="wb-prop">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : ""}>{children}</dd>
    </div>
  );
}

function RunInspector({ spine, plugins, onSelect }) {
  const run = spine?.run;
  if (!spine) return <InspectorShell title="Run"><p className="wb-muted">Loading…</p></InspectorShell>;
  if (!run) return <InspectorShell title="No recorded run"><p className="wb-muted">Pick a tool on the left to run it.</p></InspectorShell>;
  const names = new Set((plugins ?? []).map((p) => p.name));
  const router = (name, label) => (names.has(name)
    ? <button type="button" className="wb-inline-link" onClick={() => onSelect({ kind: "plugin", id: name })}>{label}</button> : label);
  return (
    <InspectorShell title={run.name} sub={`rev ${run.revision} · KiCad ${run.kicad}`}>
      <dl className="wb-props">
        <Prop label="Gates">Steps {listWords(spine.gates)} stop the run on an error, before anything is routed or written.</Prop>
        <Prop label="Routing">{router("FreeRouting", "FreeRouting")} first; then {router("KiCadRoutingTools", "KiCadRoutingTools")}, then {router("Copper (copper-kicad-mcp)", "Copper")}, while DRC still reports errors.</Prop>
        <Prop label="Limits">{run.claim_boundary}</Prop>
        <Prop label="Record" mono>{run.record}</Prop>
      </dl>
      <p className="wb-muted">Select a step for its detail, or a tool on the left to run it.</p>
    </InspectorShell>
  );
}

function StepInspector({ selection, spine, plugins, onSelect }) {
  const step = spine?.steps.find((s) => s.key === selection.id);
  if (!step) return <InspectorShell title="Step"><p className="wb-muted">Loading…</p></InspectorShell>;
  const names = new Set((plugins ?? []).map((p) => p.name));
  return (
    <InspectorShell kind={step.gate ? `step ${step.n} · gate` : `step ${step.n}`} title={step.title}>
      <dl className="wb-props">
        <Prop label="Runs">
          <span className="wb-chiplist">
            {step.runs.map((r) => names.has(r)
              ? <button key={r} type="button" className="wb-chip is-link" onClick={() => onSelect({ kind: "plugin", id: r })}><Icon name="plug" size={12} />{r}</button>
              : <span key={r} className="wb-chip">{r}</span>)}
          </span>
        </Prop>
        <Prop label={step.gate ? "Stops the run on" : "Hands on when"}>{step.stops_on ?? "—"}</Prop>
        <Prop label="This run">
          <span className="wb-inline"><Outcome outcome={step.run.outcome} /> {OUTCOME_LABEL[step.run.outcome]}</span>
          <span className="wb-block-line">{step.run.line}</span>
        </Prop>
        <Prop label="Record" mono>{spine.run?.record ?? "—"}</Prop>
      </dl>
      <button type="button" className="wb-btn" onClick={() => onSelect({ kind: "tool", id: step.tool })}>
        <Icon name="tool" size={14} /> Open {toolTitle(step.tool)}
      </button>
    </InspectorShell>
  );
}

function PluginInspector({ selection, plugins, spine, onSelect }) {
  const p = (plugins ?? []).find((x) => x.name === selection.id);
  if (!p) return <InspectorShell title="Outside tool"><p className="wb-muted">Loading…</p></InspectorShell>;
  const usedAt = (spine?.steps ?? []).filter((s) => s.runs.includes(p.name));
  return (
    <InspectorShell kind={`outside tool · ${(ROLE_LABELS[p.role] ?? p.role).toLowerCase()}`} title={p.name}>
      <dl className="wb-props">
        <Prop label="Status"><span className={`wb-row-tag st-${p.status}`}>{p.status}</span></Prop>
        <Prop label="Licence" mono>{p.licence}</Prop>
        <Prop label="How HS uses it">{p.how}</Prop>
        <Prop label="Measured">{p.measured ?? "not measured"}</Prop>
        {p.record && <Prop label="Record" mono>{p.record}</Prop>}
        {usedAt.length > 0 && (
          <Prop label="Spine steps">
            <span className="wb-chiplist">
              {usedAt.map((s) => (
                <button key={s.key} type="button" className="wb-chip is-link" onClick={() => onSelect({ kind: "step", id: s.key })}>
                  <span className="mono">{String(s.n).padStart(2, "0")}</span> {s.title}
                </button>
              ))}
            </span>
          </Prop>
        )}
      </dl>
      {p.source && /^https?:\/\//.test(p.source) && (
        <a className="wb-btn" href={p.source} target="_blank" rel="noreferrer"><Icon name="external" size={14} /> Source</a>
      )}
    </InspectorShell>
  );
}

function ToolInspector({ selection, tools, formValues, formErrors, onFieldChange, onLoadExample, onRun, runs }) {
  const tool = (tools ?? []).find((t) => t.name === selection.id);
  if (!tool) return <InspectorShell title="Tool"><p className="wb-muted">Loading…</p></InspectorShell>;
  const running = runs.some((r) => r.tool === tool.name && r.status === "running");
  const last = runs.find((r) => r.tool === tool.name && r.status !== "running");
  const onKey = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); onRun(tool); } };
  return (
    <InspectorShell kind={`HS tool · ${groupOf(tool.name).toLowerCase()}`} title={toolTitle(tool.name)} sub={tool.name}
      footer={
        <>
          {EXAMPLES[tool.name] && <button type="button" className="wb-btn" onClick={() => onLoadExample(tool)} disabled={running}>Load example</button>}
          <button type="button" className="wb-btn is-primary" onClick={() => onRun(tool)} disabled={running} aria-keyshortcuts="Control+Enter">
            <Icon name="play" size={12} /> {running ? "Running…" : "Run"}
          </button>
        </>
      }>
      <p className="wb-desc">{tool.description}</p>
      <div onKeyDown={onKey}>
        <SchemaForm tool={tool} values={formValues[tool.name] ?? {}} errors={formErrors[tool.name]} disabled={running}
          onChange={(field, value) => onFieldChange(tool.name, field, value)} />
      </div>
      {last && (
        <p className="wb-lastrun">
          Last run: <span className={`wb-status is-${last.status}`}>{last.status === "ok" ? "ok" : last.status === "problems" ? "problems reported" : "request failed"}</span>
          {last.ms !== null && <span className="mono"> · {fmtMs(last.ms)}</span>}
        </p>
      )}
    </InspectorShell>
  );
}

/* ---------------------------------------------------------------- Console */

export function ConsolePanel({ runs, system, activeRunId, onOpenRun, onClear, open, onToggle }) {
  const [only, setOnly] = useState("all");
  const listRef = useRef(null);
  const shown = runs.filter((r) => only === "all" || r.status === "problems" || r.status === "error");
  useEffect(() => { if (listRef.current) listRef.current.scrollTop = 0; }, [runs.length]);
  const latest = runs[0]
    ? { time: runs[0].time, level: runs[0].status, text: `${runs[0].tool} · ${lineOf(runs[0])}` }
    : system[0];
  return (
    <section className={`wb-console${open ? " is-open" : ""}`} aria-label="Console">
      <header className="wb-panel-head">
        <button type="button" className="wb-console-toggle" aria-expanded={open} onClick={onToggle}>
          <Icon name="chevron" size={12} className={open ? "is-open is-up" : ""} />
          <h2>Console</h2>
          {runs.length > 0 && <span className="wb-section-meta">{runs.length}</span>}
        </button>
        {!open && latest && (
          <span className="wb-console-latest">
            <span className={`wb-log-dot is-${latest.level}`} aria-hidden="true" />
            <span className="wb-log-text">{latest.text}</span>
          </span>
        )}
        {open && (
          <>
            <div className="wb-seg" role="group" aria-label="Show">
              <button type="button" aria-pressed={only === "all"} onClick={() => setOnly("all")}>All</button>
              <button type="button" aria-pressed={only === "problems"} onClick={() => setOnly("problems")}>Problems</button>
            </div>
            <button type="button" className="wb-ghost" onClick={onClear} disabled={!runs.length}>Clear</button>
          </>
        )}
      </header>
      {open && (
        <ol className="wb-log" ref={listRef}>
          {shown.map((r) => (
            <li key={r.id}>
              <button type="button" className={`wb-logrow is-${r.status}${r.id === activeRunId ? " is-active" : ""}`} onClick={() => onOpenRun(r.id)}>
                <span className="mono wb-log-time">{r.time}</span>
                <span className={`wb-log-dot is-${r.status}`} aria-hidden="true" />
                <span className="mono wb-log-tool">{r.tool}</span>
                <span className="wb-log-text">{lineOf(r)}</span>
                {r.ms !== null && <span className="mono wb-log-ms">{fmtMs(r.ms)}</span>}
              </button>
            </li>
          ))}
          {system.map((s, i) => (
            <li key={`s${i}`} className="wb-logrow is-system">
              <span className="mono wb-log-time">{s.time}</span>
              <span className={`wb-log-dot is-${s.level}`} aria-hidden="true" />
              <span className="wb-log-text">{s.text}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function lineOf(r) {
  return r.status === "running" ? "running…" : r.status === "error" ? r.error : summaryText(r.env);
}

function summaryText(env) {
  if (!env) return "";
  const s = typeof env.summary === "string" ? env.summary : env.summary ? JSON.stringify(env.summary) : "";
  const n = env.problems?.length ?? 0;
  return n ? `${s}${s ? " · " : ""}${n} problem${n === 1 ? "" : "s"}` : s;
}

/* ---------------------------------------------------------------- Command palette */

export function Palette({ open, onClose, spine, tools, plugins, onSelect }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const inputRef = useRef(null);
  useEffect(() => { if (open) { setQ(""); setI(0); } }, [open]);
  const items = useMemo(() => {
    const all = [
      ...(spine?.steps ?? []).map((s) => ({ kind: "step", id: s.key, label: `${String(s.n).padStart(2, "0")} ${s.title}`, hint: s.runs.join(" · ") })),
      ...(tools ?? []).map((t) => ({ kind: "tool", id: t.name, label: toolTitle(t.name), hint: t.name })),
      ...(plugins ?? []).map((p) => ({ kind: "plugin", id: p.name, label: p.name, hint: `${ROLE_LABELS[p.role] ?? p.role} · ${p.licence}` })),
    ];
    const query = q.trim().toLowerCase();
    if (!query) return all.slice(0, 60);
    let scored = all.map((x) => ({ x, s: score(query, x.label, x.hint) })).filter((r) => r.s > 0);
    if (scored.some((r) => r.s >= 40)) scored = scored.filter((r) => r.s >= 40);
    scored.sort((a, b) => b.s - a.s);
    return scored.slice(0, 60).map((r) => r.x);
  }, [q, spine, tools, plugins]);
  if (!open) return null;
  const choose = (item) => { if (item) { onSelect({ kind: item.kind, id: item.id }); onClose(); } };
  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(items.length - 1, x + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(items[i]); }
  };
  const KIND = { step: "Step", tool: "Tool", plugin: "Outside" };
  return (
    <div className="wb-palette-scrim" onMouseDown={onClose}>
      <div className="wb-palette" role="dialog" aria-modal="true" aria-label="Jump to" onMouseDown={(e) => e.stopPropagation()} onKeyDown={onKey}>
        <div className="wb-search is-large">
          <Icon name="search" size={16} />
          <input ref={inputRef} autoFocus value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="Jump to a step, tool or outside tool"
            aria-label="Jump to" aria-controls="wb-palette-list" aria-activedescendant={items[i] ? `bp-${i}` : undefined} spellCheck={false} />
          <kbd>Esc</kbd>
        </div>
        <ul id="wb-palette-list" role="listbox" className="wb-palette-list">
          {items.map((it, n) => (
            <li key={`${it.kind}:${it.id}`} id={`bp-${n}`} role="option" aria-selected={n === i}
              className={n === i ? "is-active" : ""} onMouseEnter={() => setI(n)} onMouseDown={(e) => { e.preventDefault(); choose(it); }}>
              <span className="wb-palette-kind">{KIND[it.kind]}</span>
              <span className="wb-palette-label">{it.label}</span>
              <span className="mono wb-palette-hint">{it.hint}</span>
            </li>
          ))}
          {!items.length && <li className="wb-palette-empty">Nothing matches.</li>}
        </ul>
      </div>
    </div>
  );
}
