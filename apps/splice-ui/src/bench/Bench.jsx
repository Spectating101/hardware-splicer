import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./bench.css";
import { fetchMeasures, fetchOutsideTools, fetchSpine, fetchTools, runTool } from "./benchApi.js";
import { EXAMPLES } from "./catalog.js";
import { argsFromValues, valuesFromArgs } from "./SchemaForm.jsx";
import { Icon } from "./icons.jsx";
import { ConsolePanel, Explorer, Inspector, Palette } from "./panels.jsx";
import { BoardView, MeasuresView, ResultView, SpineView } from "./views.jsx";

const TABS = [
  ["spine", "Spine", "spine"],
  ["board", "Board", "board"],
  ["measures", "Measured", "chart"],
  ["result", "Result", "result"],
];

const SIZES_KEY = "hs.bench.sizes.v3";
const DEFAULT_SIZES = { left: 256, right: 340, bottom: 112 };

const clock = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

function loadSizes() {
  try { return { ...DEFAULT_SIZES, ...JSON.parse(window.localStorage.getItem(SIZES_KEY) || "{}") }; } catch { return DEFAULT_SIZES; }
}

/**
 * The workbench: HS's own first screen. Explorer (spine, HS tools, outside tools) on the left, the view in the
 * middle, the Inspector on the right, every run in the Console below. Everything shown comes from the engine.
 */
export default function Bench({ onNavigate }) {
  const [tools, setTools] = useState(null);
  const [plugins, setPlugins] = useState(null);
  const [spine, setSpine] = useState(null);
  const [measures, setMeasures] = useState(null);
  const [engine, setEngine] = useState("connecting");
  const [system, setSystem] = useState([]);
  const [selection, setSelection] = useState({ kind: "step", id: "drc" });
  const [tab, setTab] = useState("spine");
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [formErrors, setFormErrors] = useState({});
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [sizes, setSizes] = useState(loadSizes);
  const [pane, setPane] = useState("view");
  const seq = useRef(0);

  const log = useCallback((level, text) => setSystem((s) => [{ level, text, time: clock() }, ...s].slice(0, 50)), []);

  useEffect(() => {
    const ctl = new AbortController();
    const { signal } = ctl;
    Promise.allSettled([fetchTools(signal), fetchOutsideTools(signal), fetchSpine(signal), fetchMeasures(signal)]).then((res) => {
      if (signal.aborted) return;
      const [t, p, s, m] = res;
      if (t.status === "fulfilled") setTools(t.value); else setTools([]);
      if (p.status === "fulfilled") setPlugins(p.value); else setPlugins([]);
      if (s.status === "fulfilled") setSpine(s.value);
      if (m.status === "fulfilled") setMeasures(m.value);
      const failed = res.filter((r) => r.status === "rejected");
      if (failed.length === res.length) {
        setEngine("offline");
        log("error", `Engine not reachable: ${failed[0].reason?.message ?? "no answer"}`);
        return;
      }
      setEngine("connected");
      log("ok", `Engine connected · ${t.value?.length ?? 0} HS tools · ${p.value?.length ?? 0} outside tools`
        + (s.value?.run ? ` · run: ${s.value.run.name}` : ""));
      failed.forEach((f) => log("error", f.reason?.message ?? "a request failed"));
    });
    return () => ctl.abort();
  }, [log]);

  useEffect(() => {
    try { window.localStorage.setItem(SIZES_KEY, JSON.stringify(sizes)); } catch { /* viewer preference only */ }
  }, [sizes]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPaletteOpen((v) => !v); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const select = useCallback((next) => {
    setSelection(next);
    if (next.kind === "step") setTab((t) => (t === "result" ? "spine" : t));
    setPane("inspector");
  }, []);

  const onFieldChange = useCallback((toolName, field, value) => {
    setFormValues((v) => ({ ...v, [toolName]: { ...(v[toolName] ?? {}), [field]: value } }));
    setFormErrors((e) => (e[toolName]?.[field] ? { ...e, [toolName]: { ...e[toolName], [field]: undefined } } : e));
  }, []);

  const onLoadExample = useCallback((tool) => {
    setFormValues((v) => ({ ...v, [tool.name]: valuesFromArgs(tool.input_schema, EXAMPLES[tool.name]) }));
    setFormErrors((e) => ({ ...e, [tool.name]: {} }));
  }, []);

  const onRun = useCallback(async (tool) => {
    const { args, errors } = argsFromValues(tool.input_schema, formValues[tool.name]);
    if (Object.keys(errors).length) { setFormErrors((e) => ({ ...e, [tool.name]: errors })); return; }
    const id = `r${++seq.current}`;
    const started = performance.now();
    setRuns((r) => [{ id, tool: tool.name, args, status: "running", env: null, error: null, ms: null, time: clock() }, ...r].slice(0, 200));
    setActiveRunId(id);
    setTab("result");
    setPane("view");
    try {
      const env = await runTool(tool.name, args);
      const status = env?.ok === false || (env?.problems?.length ?? 0) > 0 ? "problems" : "ok";
      setRuns((r) => r.map((x) => (x.id === id ? { ...x, env, status, ms: performance.now() - started } : x)));
    } catch (err) {
      setRuns((r) => r.map((x) => (x.id === id ? { ...x, status: "error", error: err.message, ms: performance.now() - started } : x)));
    }
  }, [formValues]);

  const activeRun = useMemo(() => runs.find((r) => r.id === activeRunId) ?? null, [runs, activeRunId]);
  const pluginNames = useMemo(() => new Set((plugins ?? []).map((p) => p.name)), [plugins]);
  const selectPlugin = useCallback((name) => select({ kind: "plugin", id: name }), [select]);

  const startDrag = (which) => (e) => {
    e.preventDefault();
    const start = { x: e.clientX, y: e.clientY, ...sizes };
    const move = (ev) => {
      setSizes((s) => {
        if (which === "left") return { ...s, left: clamp(start.left + ev.clientX - start.x, 200, 460) };
        if (which === "right") return { ...s, right: clamp(start.right - (ev.clientX - start.x), 280, 560) };
        return { ...s, bottom: clamp(start.bottom - (ev.clientY - start.y), 96, 480) };
      });
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); document.body.classList.remove("wb-dragging"); };
    document.body.classList.add("wb-dragging");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const keyResize = (which) => (e) => {
    const d = e.key === "ArrowLeft" || e.key === "ArrowUp" ? -16 : e.key === "ArrowRight" || e.key === "ArrowDown" ? 16 : 0;
    if (!d) return;
    e.preventDefault();
    setSizes((s) => which === "left" ? { ...s, left: clamp(s.left + d, 200, 460) }
      : which === "right" ? { ...s, right: clamp(s.right - d, 280, 560) } : { ...s, bottom: clamp(s.bottom - d, 96, 480) });
  };

  const style = { "--wb-left": `${sizes.left}px`, "--wb-right": `${sizes.right}px`, "--wb-bottom": `${sizes.bottom}px` };

  return (
    <div className="hs-bench" style={style} data-testid="bench" data-pane={pane}>
      <header className="wb-top">
        <div className="wb-brand">
          <span className="wb-mark" aria-hidden="true">HS</span>
          <span className="wb-brand-name">Hardware Splicer</span>
          <span className="wb-crumb">Workbench</span>
        </div>
        <button type="button" className="wb-jump" onClick={() => setPaletteOpen(true)} aria-keyshortcuts="Control+K">
          <Icon name="search" size={14} />
          <span>Jump to a step, tool or outside tool</span>
          <kbd>Ctrl K</kbd>
        </button>
        <nav className="wb-links" aria-label="Other screens">
          <button type="button" onClick={() => onNavigate?.("home")}>Projects</button>
          <button type="button" onClick={() => onNavigate?.("library")}>Library</button>
          <button type="button" onClick={() => onNavigate?.("advanced")}>Advanced</button>
        </nav>
        <span className={`wb-engine is-${engine}`} role="status">
          <span className="wb-engine-dot" aria-hidden="true" />
          {engine === "connected" ? "Engine connected" : engine === "offline" ? "Engine offline" : "Connecting…"}
        </span>
      </header>

      <div className="wb-panes" role="tablist" aria-label="Panel">
        {[["explorer", "Browse"], ["view", "View"], ["inspector", "Inspector"], ["console", "Console"]].map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={pane === k} onClick={() => setPane(k)}>{l}</button>
        ))}
      </div>

      <div className="wb-body">
        <div className="wb-col wb-col-left">
          <Explorer spine={spine} tools={tools} plugins={plugins} selection={selection} onSelect={select} engine={engine} />
        </div>
        <div className="wb-split is-v" role="separator" aria-orientation="vertical" aria-label="Resize explorer" tabIndex={0}
          onPointerDown={startDrag("left")} onKeyDown={keyResize("left")} />
        <div className="wb-col wb-col-mid">
          <main className="wb-viewport">
            <div className="wb-tabs" role="tablist" aria-label="View">
              {TABS.map(([key, label, icon]) => (
                <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "is-active" : ""}
                  onClick={() => setTab(key)}>
                  <Icon name={icon} size={14} />{label}
                  {key === "result" && runs.some((r) => r.status === "running") && <span className="wb-tab-busy" aria-label="running" />}
                </button>
              ))}
            </div>
            <div className="wb-view" role="tabpanel">
              {tab === "spine" && <SpineView spine={spine} selectedKey={selection.kind === "step" ? selection.id : null}
                onSelectStep={(key) => select({ kind: "step", id: key })} onSelectPlugin={selectPlugin} pluginNames={pluginNames} />}
              {tab === "board" && <BoardView spine={spine} />}
              {tab === "measures" && <MeasuresView measures={measures} onSelectPlugin={selectPlugin} pluginNames={pluginNames} />}
              {tab === "result" && <ResultView run={activeRun} tools={tools} />}
            </div>
          </main>
          <div className="wb-split is-h" role="separator" aria-orientation="horizontal" aria-label="Resize console" tabIndex={0}
            onPointerDown={startDrag("bottom")} onKeyDown={keyResize("bottom")} />
          <div className="wb-col-console">
            <ConsolePanel runs={runs} system={system} activeRunId={activeRunId}
              onOpenRun={(id) => { setActiveRunId(id); setTab("result"); setPane("view"); }} onClear={() => setRuns([])} />
          </div>
        </div>
        <div className="wb-split is-v" role="separator" aria-orientation="vertical" aria-label="Resize inspector" tabIndex={0}
          onPointerDown={startDrag("right")} onKeyDown={keyResize("right")} />
        <div className="wb-col wb-col-right">
          <Inspector selection={selection} spine={spine} tools={tools} plugins={plugins} onSelect={select}
            formValues={formValues} formErrors={formErrors} onFieldChange={onFieldChange} onLoadExample={onLoadExample}
            onRun={onRun} runs={runs} />
        </div>
      </div>

      <Palette open={paletteOpen} onClose={() => setPaletteOpen(false)} spine={spine} tools={tools} plugins={plugins} onSelect={select} />
    </div>
  );
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}
