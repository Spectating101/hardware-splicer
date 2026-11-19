import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BASIS_LABELS, DEFAULT_EXPLODE, DIFF_LABELS, FIELDDECK_NARROW, TOUR,
  classifyPart, evidenceCells, formatEvidenceSource, indexFielddeck, rowsForMode, selectedPartKeys,
  evidenceLabel, ghostDeltaKey, openQuestions, shortPartName, toggleFielddeckSheet,
} from "./fielddeckLogic.js";
import { createFielddeckStage, disposeFielddeck, loadFielddeck } from "./fielddeckStage.js";
import "./fielddeckScene.css";

const INITIAL = {
  mode: "5", explode: DEFAULT_EXPLODE, selected: null, stop: 0, cue: null,
  hero: null, faceView: false, blockers: true, touring: false,
};
const LEGEND = [["Shape source", BASIS_LABELS], ["Change", DIFF_LABELS]];
const MODES = [["7", "7-inch"], ["5", "5-inch"], ["compare", "Compare"]];
const EVIDENCE_STATES = new Set(["datasheet", "assumed", "computed", "unknown"]);
let introSeen = false;

function EvidenceSource({ source: { href, label } }) {
  return href ? <a href={href} title={href} target="_blank" rel="noreferrer">{label}</a> : label;
}

function hasNumericValue({ value, state }) {
  return state !== "unknown" && (typeof value === "number"
    || Array.isArray(value) && value.some((item) => typeof item === "number"));
}

export function EvidenceRows({ evidence }) {
  return (
    <dl className="fd-evidence" aria-label="Evidence">
      {evidence.map((row, i) => {
        const [field, value, state, source] = evidenceCells(row);
        const label = evidenceLabel(field);
        const unknownMethod = !row.method || row.method === "unknown";
        const unknown = value === "unknown" && state === "unknown" && source.label === "unknown" && unknownMethod;
        return (
          <div key={`${field}:${i}`} className="fd-evidence-row" data-inspector-item title={field}>
            <dt>{label}</dt>
            <dd className="fd-evidence-state">{unknown ? "Unknown" : state}</dd>
            {!unknown && <>
              <dd className="fd-evidence-value" data-numeric={hasNumericValue(row)}>{value}</dd>
              <dd className="fd-evidence-source"><EvidenceSource source={source} /></dd>
            </>}
          </div>
        );
      })}
    </dl>
  );
}

function nameOf(row) {
  return row?.part ? shortPartName(row.part, row.revision) : row?.link?.label;
}

function statusOf(row) {
  if (!row) return "";
  if (row.link) return "Interface · physical fit unknown";
  const { basis } = classifyPart(row.part);
  const diff = DIFF_LABELS[row.delta]?.toLowerCase() ?? "change unknown";
  const fit = row.part.evidence.find(({ field }) => field === "physical_fit")?.state;
  return `${BASIS_LABELS[basis]} · ${diff} · physical fit ${EVIDENCE_STATES.has(fit) ? fit : "unknown"}`;
}

function questionText(reason) {
  if (/^[a-z]+(?:_[a-z]+)+$/.test(reason)) return evidenceLabel(reason);
  return reason.charAt(0).toUpperCase() + reason.slice(1);
}

function QuestionNumber({ number }) {
  return <span className="fd-question-numbers">{number}</span>;
}

function Inspector({ row, index, questions, open }) {
  const scroll = useRef(null);
  const [more, setMore] = useState(0);
  useLayoutEffect(() => {
    const panel = scroll.current;
    if (!open) return;
    panel.scrollTop = 0;
    const update = () => {
      const overflowing = panel.scrollHeight - panel.scrollTop > panel.clientHeight + 1;
      const bottom = panel.getBoundingClientRect().bottom - 24;
      if (!overflowing) {
        setMore(0);
        return;
      }
      setMore([...panel.querySelectorAll("[data-inspector-item]")].filter(
        (item) => item.getBoundingClientRect().bottom > bottom,
      ).length);
    };
    update();
    panel.addEventListener("scroll", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(panel);
    return () => {
      panel.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [row, questions, open]);

  const { part, link, revision } = row ?? {};
  return (
    <aside className="fd-inspector fd-panel" id="fd-inspector" aria-label="Selection details" hidden={!open}>
      <div className="fd-inspector-scroll" id="fd-inspector-content" ref={scroll} tabIndex={0}>
        {!row ? <p className="fd-empty">Select a part or interface to inspect its evidence.</p> : <>
          <h2>{part?.label ?? link.label}</h2>
          <p className="fd-status">{statusOf(row)}</p>
          {questions.length > 0 && <>
            <h3>Open questions</h3>
            <ul className="fd-checks">
              {questions.map(({ reason, number }) => (
                <li data-inspector-item key={number}>
                  <QuestionNumber number={number} />{" "}<span>{questionText(reason)}</span>
                </li>
              ))}
            </ul>
          </>}
          {link ? <>
            <h3>Routing unknown</h3>
            <dl className="fd-endpoints">
              {[["A", link.from_part_id], ["B", link.to_part_id]].map(([letter, id]) => (
                <div key={letter} data-inspector-item>
                  <dt>{letter}</dt><dd>{index.byPart.get(`${revision}:${id}`)?.part.label ?? id ?? "Unknown endpoint"}</dd>
                </div>
              ))}
            </dl>
            {link.source && <div data-inspector-item><EvidenceSource source={formatEvidenceSource(link.source)} /></div>}
          </> : <>
            <h3>Evidence</h3>
            <EvidenceRows evidence={part.evidence} />
            {part.explode_derived && <p className="fd-note" data-inspector-item>Presentation offset</p>}
          </>}
        </>}
      </div>
      {open && more > 0 && <div className="fd-inspector-more"><span>{more} more</span></div>}
    </aside>
  );
}

function PartTree({ rows, view, questions, counts, blockersOnly, selectedKeys, linked, onSelect }) {
  const [unchangedOpen, setUnchangedOpen] = useState(false);
  const tree = useRef(null);
  const groups = Object.entries(DIFF_LABELS).map(([kind, label]) => ({
    kind, label, items: rows.filter(({ part, delta }) => part && (delta ?? "unchanged") === kind),
  }));
  groups.splice(3, 0,
    { kind: "interface", label: "Interfaces", items: rows.filter(({ link }) => link) },
    { kind: "blocker", label: "Blockers", items: questions },
  );

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
      {groups.filter(({ kind }) => !blockersOnly || kind === "blocker").map(({ kind, label, items }) => {
        const count = kind === "blocker" ? questions.length : counts?.[kind] ?? items.length;
        const heading = <>{label} <span className="fd-count">{count}</span></>;
        return (
          <section className="fd-tree-group" aria-label={label} key={kind}>
            <h3>{kind === "unchanged" ? (
              <button type="button" aria-expanded={unchangedOpen} aria-controls="fd-unchanged"
                onClick={() => setUnchangedOpen(!unchangedOpen)}>{heading}</button>
            ) : heading}</h3>
            <ul id={kind === "unchanged" ? "fd-unchanged" : undefined} hidden={kind === "unchanged" && !unchangedOpen}>
              {items.map((row) => (
                <li key={row.number ?? row.key}>
                  <button type="button" aria-pressed={row.key === view.selected}
                    data-endpoint={selectedKeys.includes(row.key) && row.key !== view.selected}
                    data-row={row.key} data-kind={kind} onClick={() => onSelect(row.key)}>
                    {row.number ? <QuestionNumber number={row.number} /> : <span className="fd-swatch" aria-hidden="true" />}
                    <span className="fd-tree-label">
                      {row.reason ? questionText(row.reason) : nameOf(row)}
                    </span>
                    {row.part && !linked.has(row.key) && <small>Not linked</small>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function Annotations({ labels, selection, endpoints, pins, faceView, onSelect }) {
  return (
    <div className="fd-annotations" aria-label="Scene callouts">
      <svg className="fd-leaders" aria-hidden="true">
        {labels.map(({ key, delta }, i) => (
          <g key={key} data-kind={delta} data-leader={i}><path /><circle r="1.5" /></g>
        ))}
        <path className="fd-pin-leaders" data-pin-leaders="" />
        {faceView && ["7", "5"].map((revision) => (
          <g className="fd-dimensions" data-dimensions={revision} key={revision}
            data-kind={revision === "7" ? "removed" : "added"}>
            <path /><text /><text />
          </g>
        ))}
        {selection?.part && <path className="fd-bracket" data-bracket={selection.key} />}
      </svg>
      {labels.map((row) => <span className="fd-label" key={row.key} data-anchor={row.key}>{nameOf(row)}</span>)}
      {pins.map(({ key, reason, number }) => (
        <div className="fd-pin-position" key={number} data-pin-anchor={key}>
          <button className="fd-pin" type="button" data-question-number={number}
            aria-label={`Open question ${number}`} title={questionText(reason)} onClick={() => onSelect(key)}><span>{number}</span></button>
        </div>
      ))}
      {endpoints.map(([letter, key]) => key && (
        <div className="fd-pin-position" key={letter} data-pin-anchor={key}>
          <span className="fd-endpoint" aria-label={`Endpoint ${letter}`}>{letter}</span>
        </div>
      ))}
      {endpoints.length > 0 && (
        <div className="fd-route-position" data-route-label="" data-from={endpoints[0][1]} data-to={endpoints[1][1]}>
          <span className="fd-label">Routing unknown</span>
        </div>
      )}
    </div>
  );
}

export default function FieldDeckScene({ onExit }) {
  const host = useRef(null);
  const stage = useRef(null);
  const current = useRef(null);
  const [assets, setAssets] = useState(null);
  const [linked, setLinked] = useState(new Set());
  const [rendered, setRendered] = useState(false);
  const [stageError, setStageError] = useState("");
  const [view, setView] = useState(INITIAL);
  const [desktopTreeOpen, setDesktopTreeOpen] = useState(true);
  const [blockersOnly, setBlockersOnly] = useState(false);
  const [narrow, setNarrow] = useState(() => window.matchMedia(FIELDDECK_NARROW).matches);
  const [keyOpen, setKeyOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [sheet, setSheet] = useState(null);
  const [explodeMotion, setExplodeMotion] = useState(null);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);

  useEffect(() => {
    const media = window.matchMedia(FIELDDECK_NARROW);
    const change = () => setNarrow(media.matches);
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
  const revision = view.mode === "7" ? "7" : "5";
  const allQuestions = useMemo(() => openQuestions(sidecars, index), [sidecars, index]);
  const displayedKeys = useMemo(() => new Set(rows.map(({ key }) => key)), [rows]);
  const questions = useMemo(() => allQuestions.flatMap(({ keys, ...question }) => {
    const matching = [...keys].filter((key) => view.mode === "compare" || key.startsWith(`${revision}:`));
    if (!matching.length) return [];
    // An older revision's check can still be inspected from its visible counterpart.
    const visible = matching.filter((key) => displayedKeys.has(key));
    const fallback = view.mode === "compare" ? matching[0].replace(/^7:/, "5:") : matching[0];
    const key = visible[0] ?? (displayedKeys.has(fallback) ? fallback : matching[0]);
    return [{ ...question, key, keys: visible }];
  }), [allQuestions, displayedKeys, revision, view.mode]);
  const selectionQuestions = useMemo(() => questions.filter(
    ({ key, keys }) => key === view.selected || keys.includes(view.selected),
  ), [questions, view.selected]);
  const treeOpen = narrow ? sheet === "parts" || sheet === "blockers" : desktopTreeOpen;
  const inspectorOpen = !narrow || sheet === "details";
  const selectedKeys = useMemo(() => selectedPartKeys(index, selection), [index, selection]);
  const labels = view.faceView ? [] : rows.filter((row) => row.part && linked.has(row.key) && (row.key === selection?.key
    || row.part.part_id === "display"));
  const pins = view.blockers && !view.faceView ? questions.flatMap((question) => {
    const key = question.key;
    return linked.has(key) && index.byKey.get(key)?.part && displayedKeys.has(key) ? [question] : [];
  }) : [];
  const endpoints = selection?.link && !view.faceView ? [["A", selection.link.from_part_id], ["B", selection.link.to_part_id]]
    .map(([letter, id]) => [letter, index.byPart.get(`${selection.revision}:${id}`)?.key]) : [];
  const comparisonAvailable = sidecars["5"]?.revision_diff?.status === "available";
  const comparisonRenderable = comparisonAvailable
    && [...linked].some((key) => key.startsWith("7:")) && [...linked].some((key) => key.startsWith("5:"));

  function finishIntro() {
    setView((old) => ({
      ...old, mode: "compare", explode: DEFAULT_EXPLODE, hero: null, blockers: true,
      selected: index.byPart.get("5:display")?.key ?? null,
    }));
  }

  function select(key) {
    setView((old) => ({ ...old, selected: key, cue: null, hero: null, touring: false, blockers: true }));
  }
  current.current = { view, reduced, finishIntro, select };

  useLayoutEffect(() => {
    if (!assets) return undefined;
    const available = Object.keys(assets).filter((rev) => assets[rev].gltf && assets[rev].sidecar);
    let runtime;
    if (available.length) {
      try {
        runtime = createFielddeckStage(host.current, assets, index, {
          onFrame: () => setRendered(true),
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
      setView({ ...INITIAL, mode: "compare", hero: performance.now(), blockers: false });
    } else if (canPlay) {
      introSeen = true;
      current.current.finishIntro();
    } else {
      const mode = hasRevision("5") || !hasRevision("7") && sidecars["5"] ? "5" : "7";
      setView({ ...INITIAL, mode, selected: index.byPart.get(`${mode}:display`)?.key ?? null });
    }
    return () => {
      stage.current = null;
      runtime?.dispose();
    };
  }, [assets, index, sidecars, comparisonAvailable]);

  useLayoutEffect(() => {
    stage.current?.update({
      mode: view.mode, explode: view.explode, explodeMotion, heroStart: view.hero,
      selectedKeys, cameraCue: view.cue, reduced, faceView: view.faceView,
      ghostDeltaKey: ghostDeltaKey(index, view.mode, selection),
    });
  }, [assets, view, selectedKeys, reduced, explodeMotion, treeOpen, inspectorOpen, narrow, blockersOnly, sheet, keyOpen, index, selection]);

  useEffect(() => {
    if (view.hero == null) return undefined;
    if (reduced) {
      current.current.finishIntro();
      return undefined;
    }
    const finish = () => current.current.finishIntro();
    const timer = window.setTimeout(finish, Math.max(0, 1100 - (performance.now() - view.hero)));
    window.addEventListener("pointerdown", finish, true);
    window.addEventListener("wheel", finish, { capture: true, passive: true });
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", finish, true);
      window.removeEventListener("wheel", finish, true);
    };
  }, [view.hero, reduced]);

  function changeMode(mode) {
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
    setMoreOpen(false);
    setExplodeMotion(null);
    setView((old) => {
      const mode = stop.diff && comparisonAvailable && (comparisonRenderable || !rendered) ? "compare" : old.mode;
      const rev = mode === "7" ? "7" : "5";
      const selected = stop.partId ? index.byPart.get(`${rev}:${stop.partId}`)
        : stop.interfaceId ? index.byKey.get(`${rev}:link:${stop.interfaceId}`)
          : rowsForMode(index, mode).find((row) => row.part && row.delta === stop.diff);
      return {
        ...old, mode, explode: stop.interfaceId ? 0.45 : 1, hero: null,
        stop: stopIndex, faceView: false, selected: selected?.key ?? null, touring,
        cue: { stopIndex }, blockers: true,
      };
    });
  }

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
  const modelVisible = rendered && [...linked].some((key) => key.startsWith(`${revision}:`));
  const loading = !assets || linked.size > 0 && !rendered;
  const errors = [...(assets ? Object.values(assets).map((revision) => revision.error).filter(Boolean) : []),
    ...(stageError ? [stageError] : [])];
  const canChoose = ([mode]) => {
    if (mode === "compare") return comparisonAvailable && (comparisonRenderable || !rendered);
    return Boolean(sidecars[mode]);
  };

  function onKeyDown(event) {
    if (playing) current.current.finishIntro();
    if (event.key === "Escape") {
      setKeyOpen(false);
      setMoreOpen(false);
    }
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

  const filtered = narrow ? sheet === "blockers" : blockersOnly;

  function toggleBlockers() {
    if (narrow) setSheet((old) => toggleFielddeckSheet(old, "blockers"));
    else {
      setBlockersOnly(!filtered);
      setDesktopTreeOpen(true);
    }
  }

  return (
    <section className="fd-scene fielddeck-route" aria-labelledby="fd-title" data-testid="fielddeck-scene"
      data-scene-status={playing ? "hero" : modelVisible ? "settled" : loading ? "loading" : "unavailable"}>
      <div className="fd-stage" ref={host} tabIndex={0} aria-label="Fielddeck stage">
        <header className="fd-header">
          <div>
            {onExit && <button className="fd-exit" type="button" aria-label="Back to home" onClick={onExit}>←</button>}
            <h1 id="fd-title">Fielddeck display swap</h1>
            {!narrow && <span className="fd-revision">7-inch → 5-inch</span>}
          </div>
          <button className="fd-validation" type="button" aria-pressed={filtered} aria-controls="fd-tree"
            onClick={toggleBlockers}>
            {narrow ? <>
              <span><span className="fd-count">{questions.length}</span> questions</span>
              <span>Fit unknown</span>
            </> : <>Physical fit unknown · <span className="fd-count">{questions.length}</span> open questions</>}
          </button>
        </header>

        <aside className="fd-tree fd-panel" id="fd-tree" aria-label="Part tree" hidden={narrow && !treeOpen}>
          {!narrow && <h2><button type="button" aria-expanded={treeOpen} aria-controls="fd-tree-content"
            onClick={() => { setDesktopTreeOpen(!treeOpen); setBlockersOnly(false); }}>Assembly</button></h2>}
          <div className="fd-panel-content" id="fd-tree-content" hidden={!treeOpen}>
            <PartTree rows={rows} view={view} selectedKeys={selectedKeys} linked={linked} onSelect={select}
              questions={questions} blockersOnly={filtered} counts={view.mode === "compare" ? sidecars["5"]?.revision_diff?.counts : null} />
          </div>
        </aside>
        <Inspector row={selection} index={index} questions={selectionQuestions} open={inspectorOpen} />

        {!modelVisible && <div className="fd-stage-message" role="status">
          {loading ? "Loading Fielddeck models…" : errors.join(" ") || "Fielddeck model unavailable."}
        </div>}
        {modelVisible && errors.length > 0 && <p className="fd-stage-warning" role="status">{errors.join(" ")}</p>}
        {playing && <button className="fd-skip" type="button" onClick={finishIntro}>Skip intro</button>}

        <Annotations labels={labels} selection={view.faceView ? null : selection} endpoints={endpoints}
          pins={pins} faceView={view.faceView} onSelect={select} />
        <div className="fd-bottom">
          {assets && (
            <div className="fd-controls" data-intro={playing}>
              <div className="fd-modes" role="group" aria-label="Revision">
                {MODES.filter(canChoose).map(([mode, label]) => (
                  <button key={mode} type="button"
                    aria-pressed={view.mode === mode} onClick={() => changeMode(mode)}>
                    {label}
                  </button>
                ))}
              </div>
              {narrow && <button className="fd-more" type="button" aria-expanded={moreOpen}
                aria-controls="fd-options" onClick={() => setMoreOpen(!moreOpen)}>More</button>}
              <div className="fd-options" id="fd-options" hidden={narrow && !moreOpen}>
                {(modelVisible || playing) && <div className="fd-explode">
                  <label htmlFor="fd-explode">Explode</label>
                  <input id="fd-explode" type="range" min="0" max="1" step="0.01" value={view.explode}
                    onChange={(event) => {
                      setExplodeMotion(null);
                      setView((old) => ({ ...old, explode: Number(event.target.value), cue: null, touring: false, blockers: true }));
                    }} />
                  <output htmlFor="fd-explode">{Math.round(view.explode * 100)}%</output>
                  {!narrow && <button type="button" onClick={() => {
                    setView((old) => ({ ...old, touring: false, blockers: true }));
                    setExplodeMotion({ from: view.explode, to: view.explode > 0 ? 0 : 1, start: performance.now() });
                  }}>{view.explode > 0 ? "Collapse" : "Explode view"}</button>}
                </div>}
                {comparisonRenderable && <button type="button" onClick={() => {
                  setView((old) => ({ ...old, faceView: !old.faceView, touring: false }));
                  setMoreOpen(false);
                }}>{view.faceView ? "Back to 3D" : "Face view"}</button>}
                {narrow && <button type="button" aria-expanded={keyOpen} aria-controls="fd-legend"
                  onClick={() => setKeyOpen(!keyOpen)}>Key</button>}
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
            </div>
          )}
        </div>
        <div className="fd-legend" id="fd-legend" aria-label="Material legend" hidden={narrow && !keyOpen}>
          {LEGEND.map(([label, kinds]) => (
            <div key={label} role="group" aria-label={label}>
              <strong>{label}</strong>
              {Object.entries(kinds).map(([kind, text]) => (
                <span key={kind} data-kind={kind}><i className="fd-swatch" aria-hidden="true" />{text}</span>
              ))}
            </div>
          ))}
        </div>
        <div className="fd-sheet" hidden={!narrow}>
          <div className="fd-peek">
            <strong>{nameOf(selection) ?? "Select a part or interface"}</strong>
            {selection && <span className="fd-status">{statusOf(selection)}</span>}
            <span><span className="fd-question-numbers">{selectionQuestions.length}</span> open questions</span>
          </div>
          <div className="fd-sheets" role="group" aria-label="Scene panels">
            {[["details", "Inspector"], ["parts", "Parts"], ["blockers", "Blockers"]].map(([id, label]) => (
              <button key={id} type="button" aria-expanded={sheet === id}
                aria-controls={id === "details" ? "fd-inspector" : "fd-tree"}
                onClick={() => setSheet((old) => toggleFielddeckSheet(old, id))}>{label}</button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
