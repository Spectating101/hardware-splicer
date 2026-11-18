import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BASIS_LABELS, DEFAULT_EXPLODE, DIFF_LABELS, TOUR, VALIDATION_LABEL, classifyPart, evidenceCells,
  formatEvidenceSource, indexFielddeck, rowsForMode, selectedPartKeys,
} from "./fielddeckLogic.js";
import { createFielddeckStage, disposeFielddeck, loadFielddeck } from "./fielddeckStage.js";
import "./fielddeckScene.css";

const INITIAL = {
  mode: "5", explode: 0, selected: null, stop: 0, cue: null,
  hero: null, blockers: true, showRemoved: true, touring: false,
};
const LEGEND = [
  ["custom", "CAD part"], ["vendor_step", "Vendor model"], ["envelope", "Envelope"],
  ["changed", "Geometry changed"], ["removed", "Removed"], ["added", "Added"], ["unchanged", "Unchanged"],
];
const MODES = [["7", "7-inch"], ["5", "5-inch"], ["compare", "Compare"]];
let introSeen = false;

function EvidenceSource({ source: { href, label } }) {
  return href ? <a href={href} title={href} target="_blank" rel="noreferrer">{label}</a> : label;
}

function hasNumericValue({ value, state }) {
  return state !== "unknown" && (typeof value === "number"
    || Array.isArray(value) && value.some((item) => typeof item === "number"));
}

function CalloutEvidence({ fact }) {
  const [field, value, state, source] = evidenceCells(fact);
  return (
    <div className="fd-callout-evidence">
      <span data-numeric={hasNumericValue(fact)}>{state === "unknown" ? field : value}</span>
      {" · "}{state}
      {source.href && <> · <EvidenceSource source={source} /></>}
    </div>
  );
}

export function EvidenceRows({ evidence }) {
  return (
    <dl className="fd-evidence" aria-label="Evidence">
      {evidence.map((row, i) => {
        const [field, value, state, source] = evidenceCells(row);
        return (
          <div key={`${field}:${i}`} className="fd-evidence-row">
            <dt>{field}</dt>
            <dd className="fd-evidence-value" data-numeric={hasNumericValue(row)}>{value}</dd>
            <dd className="fd-evidence-state" data-unknown={state === "unknown"}>{state}</dd>
            <dd className="fd-evidence-source"><EvidenceSource source={source} /></dd>
          </div>
        );
      })}
    </dl>
  );
}

function PartCard({ row, mode, linked, index }) {
  if (!row) return <p className="fd-empty">Select a part or interface to inspect its evidence.</p>;
  if (row.link) {
    const { label, from_part_id, to_part_id, bom_line, open_checks, source } = row.link;
    const labelFor = (id) => index.byPart.get(`${row.revision}:${id}`)?.part.label ?? id ?? "unknown";
    return (
      <>
        <h3>{label}</h3>
        <p className="fd-note">{labelFor(from_part_id)} → {labelFor(to_part_id)}</p>
        <dl className="fd-meta">
          <dt>BOM line</dt><dd>{bom_line ?? "unknown"}</dd>
          {source && <><dt>Source</dt><dd><EvidenceSource source={formatEvidenceSource(source)} /></dd></>}
        </dl>
        <h4>Open checks</h4>
        {open_checks.length ? (
          <ul className="fd-checks">{open_checks.map((check, i) => <li key={i}>{check}</li>)}</ul>
        ) : <p className="fd-empty">No open checks recorded.</p>}
      </>
    );
  }
  const { part } = row;
  const { basis, diff } = classifyPart(part, row.delta, mode);
  return (
    <>
      <div className="fd-tags">
        <span className="fd-tag" data-kind={basis}>{BASIS_LABELS[basis]}</span>
        {diff && <span className="fd-tag" data-kind={diff}>{DIFF_LABELS[diff]}</span>}
      </div>
      <h3>{part.label}</h3>
      <dl className="fd-meta">
        <dt>Geometry basis</dt><dd>{part.geometry_basis ?? "unknown"}</dd>
        <dt>BOM line</dt><dd>{part.bom_line ?? "unknown"}</dd>
        {!linked.has(row.key) && <><dt>Scene</dt><dd>not linked</dd></>}
      </dl>
      {part.explode_derived && <p className="fd-note">Presentation offset, not assembly order</p>}
      <h4>Evidence</h4>
      <EvidenceRows evidence={part.evidence} />
    </>
  );
}

function PartTree({ rows, view, selectedKeys, linked, onSelect }) {
  const tree = useRef(null);
  useLayoutEffect(() => {
    const scroller = tree.current;
    const row = scroller?.querySelector('[aria-pressed="true"]');
    if (!row) return;
    const rect = row.getBoundingClientRect();
    const bounds = scroller.getBoundingClientRect();
    if (rect.top < bounds.top) scroller.scrollTop -= bounds.top - rect.top;
    if (rect.bottom > bounds.bottom) scroller.scrollTop += rect.bottom - bounds.bottom;
  }, [view.selected, view.mode]);

  return (
    <div className="fd-tree-scroll" ref={tree}>
      {[["Parts", rows.filter((row) => row.part)], ["Interfaces", rows.filter((row) => row.link)]]
        .map(([label, items]) => (
          <div className="fd-tree-group" key={label}>
            <h3>{label}</h3>
            <ul>
              {items.map((row) => {
                const diff = view.mode === "compare" ? row.delta : undefined;
                const kind = diff ?? row.part?.geometry_basis ?? "interface";
                return (
                  <li key={row.key}>
                    <button
                      type="button"
                      aria-pressed={row.key === view.selected}
                      data-endpoint={selectedKeys.includes(row.key) && row.key !== view.selected}
                      data-row={row.key}
                      data-kind={kind}
                      onClick={() => onSelect(row.key)}
                    >
                      <span className="fd-swatch" aria-hidden="true" />
                      <span className="fd-tree-label">{row.part?.label ?? row.link.label}</span>
                      {row.part && !linked.has(row.key) && <small>not linked</small>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
    </div>
  );
}

function sceneCallouts(index, sidecars, view, linked) {
  const items = new Map();
  const stop = TOUR[view.stop];
  function add(row, reasons = []) {
    if (!row) return;
    const anchor = selectedPartKeys(index, row).find((key) => linked.has(key));
    if (!anchor) return;
    const basis = row.part && classifyPart(row.part, row.delta, view.mode);
    const fact = row.part?.evidence.find(({ field, state }) => field === "landscape_glass_mm" && state !== "unknown")
      ?? row.part?.evidence.find(({ field }) => field === "geometry_reference")
      ?? row.part?.evidence.find(({ field, state }) => field === "print_dimensions_mm" && state !== "unknown")
      ?? row.part?.evidence.find(({ field }) => field === "physical_fit");
    const current = items.get(anchor);
    if (current) {
      current.reasons.push(...reasons);
      return;
    }
    items.set(anchor, {
      key: row.key, anchor, kind: basis?.diff ?? basis?.basis ?? "interface",
      tag: basis?.diff ? DIFF_LABELS[basis.diff] : row.part ? BASIS_LABELS[basis.basis] : "Interface",
      basisTag: basis?.diff && basis.basis,
      title: row.part?.label ?? row.link.label,
      fact,
      reasons: [...reasons],
    });
  }
  function addStopBlockers(revision, row) {
    if (!row) return;
    const reasons = sidecars[revision]?.blockers
      .filter((blocker) => row.part ? blocker.part_id === row.part.part_id
        : blocker.interface_id === row.link.interface_id)
      .map(({ reason }) => reason);
    if (reasons?.length) add(row, reasons);
  }
  if (view.blockers || !view.cue) add(index.byKey.get(view.selected));
  if (view.blockers) {
    const revision = view.mode === "7" ? "7" : "5";
    const row = stop.partId ? index.byPart.get(`${revision}:${stop.partId}`)
      : index.byKey.get(`${revision}:link:${stop.interfaceId}`);
    addStopBlockers(revision, row);
    if (view.mode === "compare" && view.stop === 0 && view.showRemoved) {
      const removed = index.byPart.get("7:display");
      if (removed?.delta === "removed") addStopBlockers("7", removed);
    }
  }
  return [...items.values()].slice(0, 4);
}

function Callouts({ items }) {
  if (!items.length) return null;
  return (
    <div className="fd-annotations" aria-label="Scene callouts">
      <svg className="fd-leaders" aria-hidden="true">
        {items.map((item, i) => (
          <g key={item.key} data-kind={item.kind} data-leader={i}>
            <path /><circle r="3.5" />
          </g>
        ))}
      </svg>
      {items.map((item, i) => (
        <div key={item.key} className="fd-callout" data-kind={item.kind} data-anchor={item.anchor} data-callout={i}>
          <div className="fd-callout-inner">
            <div className="fd-tags">
              <span className="fd-tag" data-kind={item.kind}>{item.tag}</span>
              {item.basisTag && <span className="fd-tag" data-kind={item.basisTag}>{BASIS_LABELS[item.basisTag]}</span>}
            </div>
            <strong title={item.title}>{item.title}</strong>
            {item.fact && <CalloutEvidence fact={item.fact} />}
            {item.reasons.length > 0 && (
              <ul>
                {item.reasons.slice(0, 3).map((reason, j) => <li key={j} title={reason}>{reason}</li>)}
              </ul>
            )}
            {item.reasons.length > 3 && (
              <span className="fd-callout-more" title={item.reasons.slice(3).join("\n")}>
                +{item.reasons.length - 3} more
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function FieldDeckScene() {
  const host = useRef(null);
  const stage = useRef(null);
  const current = useRef(null);
  const [assets, setAssets] = useState(null);
  const [linked, setLinked] = useState(new Set());
  const [rendered, setRendered] = useState(false);
  const [stageError, setStageError] = useState("");
  const [view, setView] = useState(INITIAL);
  const [treeOpen, setTreeOpen] = useState(false);
  const [collapsedSelection, setCollapsedSelection] = useState(null);
  const [explodeMotion, setExplodeMotion] = useState(null);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let loaded;
    loadFielddeck(controller.signal).then((result) => {
      if (controller.signal.aborted) disposeFielddeck(result);
      else {
        loaded = result;
        setAssets(result);
      }
    });
    return () => {
      controller.abort();
      if (loaded) disposeFielddeck(loaded);
    };
  }, []);

  const sidecars = useMemo(() => ({
    "7": assets?.["7"].sidecar, "5": assets?.["5"].sidecar,
  }), [assets]);
  const index = useMemo(() => indexFielddeck(sidecars), [sidecars]);
  const rows = useMemo(() => rowsForMode(index, view.mode), [index, view.mode]);
  const selection = index.byKey.get(view.selected);
  const inspectorOpen = Boolean(selection) && collapsedSelection !== view.selected;
  const selectedKeys = useMemo(() => selectedPartKeys(index, selection), [index, selection]);
  const comparisonAvailable = sidecars["5"]?.revision_diff?.status === "available";
  const comparisonRenderable = comparisonAvailable
    && [...linked].some((key) => key.startsWith("7:")) && [...linked].some((key) => key.startsWith("5:"));

  function finishIntro() {
    setView((old) => ({
      ...old, mode: "compare", explode: DEFAULT_EXPLODE, hero: null, blockers: true, showRemoved: true,
      selected: index.byPart.get("5:display")?.key ?? null,
    }));
  }

  function select(key) {
    setCollapsedSelection(null);
    setView((old) => ({ ...old, selected: key, cue: null, hero: null, touring: false, blockers: true }));
  }
  current.current = { view, reduced, finishIntro, select };

  useLayoutEffect(() => {
    if (!assets) return undefined;
    const available = Object.keys(assets).filter((rev) => assets[rev].gltf && assets[rev].sidecar);
    let playIntro = false;
    let runtime;
    if (available.length) {
      try {
        runtime = createFielddeckStage(host.current, assets, index, {
          onFrame: () => {
            setRendered(true);
            if (playIntro) setView((old) => ({ ...old, hero: performance.now() }));
          },
          onInterrupt: () => current.current.finishIntro(),
          onPick: (key) => {
            if (current.current.view.hero === null && key) current.current.select(key);
          },
        });
        stage.current = runtime;
        setLinked(runtime.linked);
      } catch (error) {
        setStageError(`3D stage unavailable (${error.message}).`);
      }
    }
    const hasRevision = (rev) => [...(runtime?.linked ?? [])].some((key) => key.startsWith(`${rev}:`));
    const canPlay = comparisonAvailable && hasRevision("7") && hasRevision("5");
    if (canPlay && !introSeen && !current.current.reduced) {
      introSeen = true;
      playIntro = true;
      setView({ ...INITIAL, mode: "7", blockers: false, showRemoved: false });
    } else if (canPlay) {
      introSeen = true;
      current.current.finishIntro();
    } else {
      const mode = hasRevision("5") || !hasRevision("7") && sidecars["5"] ? "5" : "7";
      setView({ ...INITIAL, mode, explode: DEFAULT_EXPLODE, selected: index.byPart.get(`${mode}:display`)?.key ?? null });
    }
    return () => {
      stage.current = null;
      runtime?.dispose();
    };
  }, [assets, index, sidecars, comparisonAvailable]);

  useLayoutEffect(() => {
    stage.current?.update({
      mode: view.mode, explode: view.explode, explodeMotion, heroStart: view.hero,
      selectedKeys, cameraCue: view.cue, reduced,
    });
  }, [assets, view, selectedKeys, reduced, explodeMotion, treeOpen, inspectorOpen]);

  useEffect(() => {
    if (view.hero == null) return undefined;
    if (reduced) {
      current.current.finishIntro();
      return undefined;
    }
    const timeline = [
      [1800, (old) => ({ ...old, mode: "compare" })],
      [2400, (old) => ({ ...old, blockers: true, selected: index.byPart.get("5:display")?.key })],
      [3200, (old) => ({ ...old, showRemoved: true })],
      [5000, () => current.current.finishIntro()],
    ];
    const timers = timeline.map(([at, apply], i) => window.setTimeout(
      () => i === timeline.length - 1 ? apply() : setView((old) => old.hero == null ? old : apply(old)),
      Math.max(0, at - (performance.now() - view.hero)),
    ));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [view.hero, index, reduced]);

  function changeMode(mode) {
    setCollapsedSelection(null);
    setView((old) => {
      const active = index.byKey.get(old.selected);
      const rev = mode === "7" ? "7" : "5";
      const key = active?.part ? index.byPart.get(`${rev}:${active.part.part_id}`)?.key
        : active?.link ? `${rev}:link:${active.link.interface_id}` : null;
      return { ...old, mode, selected: index.byKey.has(key) ? key : null, cue: null, touring: false, blockers: true };
    });
  }

  function goTo(stopIndex, touring = false) {
    const stop = TOUR[stopIndex];
    if (!stop) return;
    setExplodeMotion(null);
    setCollapsedSelection(null);
    setView((old) => {
      const mode = stop.diff && comparisonAvailable && (comparisonRenderable || !rendered) ? "compare" : old.mode;
      const rev = mode === "7" ? "7" : "5";
      const selected = stop.partId ? index.byPart.get(`${rev}:${stop.partId}`)
        : stop.interfaceId ? index.byKey.get(`${rev}:link:${stop.interfaceId}`)
          : rowsForMode(index, mode).find((row) => row.part && row.delta === stop.diff);
      return {
        ...old, mode, explode: stop.interfaceId ? 0.45 : 1, hero: null,
        stop: stopIndex, selected: selected?.key ?? null, touring,
        cue: { stopIndex }, blockers: !rendered, showRemoved: true,
      };
    });
  }

  useEffect(() => {
    if (!view.cue || view.blockers) return undefined;
    const timer = window.setTimeout(() => setView((old) => ({ ...old, blockers: true })), reduced ? 1200 : 2800);
    return () => window.clearTimeout(timer);
  }, [view.cue, view.blockers, reduced]);

  useEffect(() => {
    if (!view.touring) return undefined;
    const next = view.stop + 1;
    const timer = window.setTimeout(() => {
      if (next < TOUR.length) goTo(next, true);
      else setView((old) => ({ ...old, touring: false }));
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [view.cue, view.touring, view.stop, rendered, index, comparisonAvailable, comparisonRenderable]);

  useEffect(() => {
    if (!explodeMotion) return undefined;
    const { from, to, start } = explodeMotion;
    let frame;
    function step(now) {
      const progress = reduced ? 1 : Math.min(1, (now - start) / (to ? 1100 : 800));
      const amount = to ? 1 - (1 - progress) ** 3
        : progress < 0.5 ? 4 * progress ** 3 : 1 - (-2 * progress + 2) ** 3 / 2;
      setView((old) => ({ ...old, explode: from + (to - from) * amount, cue: null }));
      if (progress < 1) frame = requestAnimationFrame(step);
      else setExplodeMotion(null);
    }
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [explodeMotion, reduced]);

  const playing = view.hero !== null;
  const callouts = useMemo(() => sceneCallouts(index, sidecars, view, linked), [index, sidecars, view, linked]);
  const revision = view.mode === "7" ? "7" : "5";
  const blockerCount = sidecars[revision]?.blockers.length;
  const modelVisible = rendered && [...linked].some((key) => key.startsWith(`${revision}:`));
  const loading = !assets || linked.size > 0 && !rendered;
  const errors = [...(assets ? Object.values(assets).map((revision) => revision.error).filter(Boolean) : []),
    ...(stageError ? [stageError] : [])];
  const canChoose = ([mode]) => {
    if (mode === "compare") return comparisonAvailable && (comparisonRenderable || !rendered);
    return Boolean(sidecars[mode]);
  };

  function onKeyDown(event) {
    if (event.key === "Escape" && playing) current.current.finishIntro();
    if (playing || !assets || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey
      || event.target.matches?.("input, textarea, select, [contenteditable=true]")) return;
    if (["ArrowLeft", "ArrowRight", "j", "k"].includes(event.key)) {
      event.preventDefault();
      goTo(view.stop + (["ArrowRight", "j"].includes(event.key) ? 1 : -1));
    }
  }
  current.current.onKeyDown = onKeyDown;
  useEffect(() => {
    const handleKey = (event) => current.current.onKeyDown(event);
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <section className="fd-scene" aria-labelledby="fd-title" data-testid="fielddeck-scene"
      data-scene-status={playing ? "hero" : modelVisible ? "settled" : loading ? "loading" : "unavailable"}>
      <div className="fd-stage" ref={host} tabIndex={0} aria-label="Fielddeck stage">
        <header className="fd-header">
          <div>
            <h1 id="fd-title">Fielddeck display swap</h1>
            <p>7-inch → 5-inch</p>
          </div>
          <div className="fd-validation">
            <span>{VALIDATION_LABEL}</span>
            <strong>{blockerCount == null ? "Blocker count unknown" : `${blockerCount} ${blockerCount === 1 ? "blocker" : "blockers"}`}</strong>
          </div>
        </header>

        <aside className="fd-tree fd-panel" aria-label="Part tree" data-open={treeOpen}>
          <h2><button type="button" aria-expanded={treeOpen} aria-controls="fd-tree-content"
            onClick={() => setTreeOpen(!treeOpen)}>Assembly</button></h2>
          <div className="fd-panel-content" id="fd-tree-content" hidden={!treeOpen}>
            {treeOpen && <PartTree rows={rows} view={view} selectedKeys={selectedKeys} linked={linked} onSelect={select} />}
          </div>
        </aside>
        <aside className="fd-inspector fd-panel" aria-label="Selection details" data-open={inspectorOpen} hidden={!selection}>
          <h2><button type="button" aria-expanded={inspectorOpen} aria-controls="fd-inspector-content"
            onClick={() => setCollapsedSelection(inspectorOpen ? view.selected : null)}>Inspector</button></h2>
          <div className="fd-inspector-scroll" id="fd-inspector-content" hidden={!inspectorOpen}>
            <PartCard row={selection} mode={view.mode} linked={linked} index={index} />
          </div>
        </aside>

        {!modelVisible && <div className="fd-stage-message" role="status">
          {loading ? "Loading Fielddeck models…" : errors.join(" ") || "Fielddeck model unavailable."}
        </div>}
        {modelVisible && errors.length > 0 && <p className="fd-stage-warning" role="status">{errors.join(" ")}</p>}
        {playing && <button className="fd-skip" type="button" onClick={finishIntro}>Skip intro</button>}

        <div className="fd-bottom">
          <Callouts items={callouts} />
          {!playing && assets && (
            <div className="fd-controls">
              <div className="fd-modes" role="group" aria-label="Revision">
                {MODES.filter(canChoose).map(([mode, label]) => (
                  <button key={mode} type="button" aria-pressed={view.mode === mode} onClick={() => changeMode(mode)}>
                    {label}
                  </button>
                ))}
              </div>
              {modelVisible && <div className="fd-explode">
                <label htmlFor="fd-explode">Explode</label>
                <input id="fd-explode" type="range" min="0" max="1" step="0.01" value={view.explode}
                  onChange={(event) => {
                    setExplodeMotion(null);
                    setView((old) => ({ ...old, explode: Number(event.target.value), cue: null, touring: false, blockers: true }));
                  }} />
                <output htmlFor="fd-explode">{Math.round(view.explode * 100)}%</output>
                <button type="button" onClick={() => {
                  setView((old) => ({ ...old, touring: false, blockers: true }));
                  setExplodeMotion({ from: view.explode, to: view.explode > 0 ? 0 : 1, start: performance.now() });
                }}>{view.explode > 0 ? "Collapse" : "Explode view"}</button>
              </div>}
              <div className="fd-tour" role="group" aria-label="Tour">
                <button type="button" disabled={!view.stop} onClick={() => goTo(view.stop - 1)}
                  aria-label="Previous stop">←</button>
                <strong>{TOUR[view.stop].label}</strong>
                <button type="button" disabled={view.stop === TOUR.length - 1} onClick={() => goTo(view.stop + 1)}
                  aria-label="Next stop">→</button>
                <button type="button" onClick={() => view.touring
                  ? setView((old) => ({ ...old, touring: false }))
                  : goTo(0, !reduced)}>{view.touring ? "Pause tour" : "Start tour"}</button>
              </div>
            </div>
          )}
          <div className="fd-caption">
            <div className="fd-legend" aria-label="Material legend">
              {LEGEND.map(([kind, label]) => (
                <span key={kind} data-kind={kind}><i className="fd-swatch" aria-hidden="true" />{label}</span>
              ))}
              {[...index.byKey.values()].some((row) => row.part?.geometry_basis === "unknown" && linked.has(row.key))
                && <span data-kind="unknown"><i className="fd-swatch" aria-hidden="true" />Unknown geometry</span>}
            </div>
            <footer className="fd-footer">
              {modelVisible && rows.some(({ part }) => part?.explode_derived) &&
                <span>Presentation offset, not assembly order</span>}
              <span>CAD preview · dimensions in mm</span>
            </footer>
          </div>
        </div>
      </div>
    </section>
  );
}
