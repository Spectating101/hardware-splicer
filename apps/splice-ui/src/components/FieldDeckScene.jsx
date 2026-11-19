import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  BASIS_LABELS, DEFAULT_EXPLODE, DIFF_LABELS, FIELDDECK_COMPARE, FIELDDECK_NARROW,
  classifyPart, evidenceCells, formatEvidenceSource, indexFielddeck, rowsForMode, selectedPartKeys,
  countClippedItems, evidenceLabel, ghostDeltaKey, openQuestions, shortPartName, toggleFielddeckSheet,
} from "./fielddeckLogic.js";
import { createFielddeckStage, disposeFielddeck, loadFielddeck } from "./fielddeckStage.js";
import { fetchSceneManifest } from "../api.js";
import "./fielddeckScene.css";

const INITIAL = {
  mode: "5", explode: DEFAULT_EXPLODE, selected: null, stop: 0, cue: null,
  hero: null, question: null, faceView: false, blockers: true, touring: false,
};
const LEGEND = [["Shape source", BASIS_LABELS], ["Change", DIFF_LABELS]];
const MODES = [["7", "7-inch"], ["5", "5-inch"], ["compare", "Compare"]];
const FALLBACK_MANIFEST = {
  title: "Fielddeck display swap",
  subtitle: "7-inch → 5-inch",
  compare: FIELDDECK_COMPARE,
  focus: { part_id: "display", label: "Display" },
  tour: [
    { label: "Display stack", select: "display", explode: 1 },
    { label: "Cable (DSI)", select: "display-ribbon", explode: 0.45 },
    { label: "Changed parts", select: null, revision: "compare", explode: 1, diff: "changed" },
  ],
};
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
  const fit = row.part?.evidence.find(({ field }) => field === "physical_fit")?.state;
  const state = EVIDENCE_STATES.has(fit) ? fit : "unknown";
  return `Physical fit · ${state.charAt(0).toUpperCase() + state.slice(1)}`;
}

function Endpoints({ row: { link, revision }, index }) {
  return (
    <dl className="fd-endpoints">
      {[["A", link.from_part_id], ["B", link.to_part_id]].map(([letter, id]) => (
        <div key={letter} data-inspector-item>
          <dt>{letter}</dt><dd>{index.byPart.get(`${revision}:${id}`)?.part.label ?? id ?? "Unknown endpoint"}</dd>
        </div>
      ))}
    </dl>
  );
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
          {part && <p className="fd-status" data-inspector-item>
            {BASIS_LABELS[classifyPart(part).basis]} · {DIFF_LABELS[row.delta]?.toLowerCase() ?? "change unknown"}
          </p>}
          {questions.length > 0 && <>
            <h3>Open questions</h3>
            <ul className="fd-checks">
              {questions.map(({ reason, number, scope }) => (
                <li data-inspector-item key={number}>
                  <span className="fd-question-scope"><QuestionNumber number={number} /> · {scope}</span>
                  <span>{questionText(reason)}</span>
                </li>
              ))}
            </ul>
          </>}
          {link ? <>
            <h3>Endpoint components</h3>
            <Endpoints row={row} index={index} />
            <p className="fd-status" data-inspector-item>Routing unknown</p>
            {link.source && <div data-inspector-item><EvidenceSource source={formatEvidenceSource(link.source)} /></div>}
          </> : <>
            <h3>Evidence</h3>
            <EvidenceRows evidence={part.evidence.filter(({ field }) => field !== "physical_fit")} />
          </>}
        </>}
      </div>
      {open && more > 0 && <div className="fd-inspector-more"><span>{more} more</span></div>}
    </aside>
  );
}

function PartTree({ rows, view, questions, counts, blockersOnly, endpoints, linked, onSelect }) {
  const [unchangedOpen, setUnchangedOpen] = useState(false);
  const tree = useRef(null);
  const [more, setMore] = useState(0);
  const endpointFor = (key) => endpoints.find(([, endpointKey]) => endpointKey === key)?.[0];
  const groups = Object.entries(DIFF_LABELS).map(([kind, label]) => ({
    kind, label, items: rows.filter(({ part, delta }) => part && (delta ?? "unchanged") === kind),
  }));
  groups.push(
    { kind: "interface", label: "Interfaces", items: rows.filter(({ link }) => link) },
    { kind: "blocker", label: "Blockers", items: questions },
  );

  useLayoutEffect(() => {
    const panel = tree.current;
    const active = panel.querySelector('[data-active-question="true"]')
      ?? panel.querySelector('[aria-pressed="true"]');
    if (active) {
      const rect = active.getBoundingClientRect();
      const bounds = panel.getBoundingClientRect();
      if (rect.top < bounds.top) panel.scrollTop -= bounds.top - rect.top;
      if (rect.bottom > bounds.bottom - 24) panel.scrollTop += rect.bottom - bounds.bottom + 24;
    }
    const update = () => {
      const { top, bottom } = panel.getBoundingClientRect();
      const items = [...panel.querySelectorAll(blockersOnly ? '[aria-label="Blockers"] li' : "li")]
        .filter((item) => item.getClientRects().length)
        .map((item) => item.getBoundingClientRect());
      setMore(panel.scrollHeight <= panel.clientHeight + 1 ? 0
        : countClippedItems(items, { top, bottom: bottom - 24 }));
    };
    update();
    panel.addEventListener("scroll", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(panel);
    return () => {
      panel.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [view.selected, view.question, rows, blockersOnly, unchangedOpen]);

  const rowButton = (row, kind) => (
    <li key={row.number ?? row.key}>
      <button type="button" aria-pressed={!row.number && row.key === view.selected}
        data-linked={row.number ? row.number === view.question : Boolean(endpointFor(row.key))}
        data-endpoint-row={!row.number ? endpointFor(row.key) : undefined}
        data-active-question={row.number ? row.number === view.question : undefined}
        data-row={row.key} data-kind={kind} onClick={() => onSelect(row.key, row.number)}>
        {row.number ? <QuestionNumber number={row.number} />
          : endpointFor(row.key) ? <span className="fd-endpoint" aria-hidden="true">{endpointFor(row.key)}</span>
          : <span className="fd-swatch" aria-hidden="true" />}
        <span className="fd-tree-label">{row.reason ? questionText(row.reason) : nameOf(row)}</span>
        {row.part && !linked.has(row.key) && <small>Not linked</small>}
      </button>
    </li>
  );
  const selected = blockersOnly && rows.find(({ key }) => key === view.selected);
  return (
    <>
      <div className="fd-tree-scroll" ref={tree}>
        {selected && <div className="fd-tree-group"><ul>
          {rowButton(selected, selected.delta ?? "interface")}
          {rows.filter(({ key }) => endpointFor(key)).map((row) => rowButton(row, row.delta ?? "unchanged"))}
        </ul></div>}
        {groups.filter(({ kind }) => !blockersOnly || kind === "blocker").map(({ kind, label, items }) => {
          const count = kind === "blocker" ? questions.length : counts?.[kind] ?? items.length;
          const collapsed = kind === "unchanged" && !unchangedOpen;
          const shown = collapsed ? items.filter(({ key }) => key === view.selected || endpointFor(key)) : items;
          const heading = <>{label} <span className="fd-count">{kind === "unchanged" ? `(${count})` : count}</span></>;
          return (
            <section className="fd-tree-group" aria-label={label} key={kind}>
              <h3>{kind === "unchanged" ? (
                <button type="button" aria-expanded={unchangedOpen} aria-controls="fd-unchanged"
                  onClick={() => setUnchangedOpen(!unchangedOpen)}>{heading}</button>
              ) : heading}</h3>
              <ul id={kind === "unchanged" ? "fd-unchanged" : undefined} hidden={collapsed && !shown.length}>
                {shown.map((row) => rowButton(row, kind))}
              </ul>
            </section>
          );
        })}
      </div>
      {more > 0 && <div className="fd-inspector-more"><span>{more} more</span></div>}
    </>
  );
}

function Annotations({ labels, selection, endpoints, pins, faceView, base, target, onSelect }) {
  return (
    <div className="fd-annotations" aria-label="Scene callouts">
      <svg className="fd-leaders" aria-hidden="true">
        {labels.map(({ key, delta }, i) => (
          <g key={key} data-kind={delta} data-leader={i}><path /><circle r="1.5" /></g>
        ))}
        <path className="fd-pin-leaders" data-pin-leaders="" />
        {endpoints.length > 0 && <path className="fd-route-leaders" data-route-leaders="" />}
        {faceView && [base, target].map((revision) => (
          <g className="fd-dimensions" data-dimensions={revision} key={revision}
            data-kind={revision === base ? "removed" : "added"}>
            <path />
          </g>
        ))}
        {selection?.part && <>
          <path className="fd-bracket-halo" data-bracket={selection.key} />
          <path className="fd-bracket" data-bracket={selection.key} />
        </>}
      </svg>
      {faceView && <>
        {[base, target].flatMap((revision) => ["width", "height"].map((axis) => (
          <span className="fd-dimension-label" key={revision + axis} data-dimension-label={revision + axis}
            data-kind={revision === base ? "removed" : "added"} data-axis={axis} />
        )))}
        <div className="fd-footprint" data-footprint="">
          <div>{target}-inch minus {base}-inch · CAD footprint, computed</div>
          <div data-footprint-delta="" />
        </div>
      </>}
      {labels.map((row) => <span className="fd-label" key={row.key} data-anchor={row.key}
        data-endpoint-label={row.endpoint}>{row.caption ?? nameOf(row)}</span>)}
      {endpoints.map(([letter, key]) => key && (
        <div className="fd-pin-position" key={letter} data-pin-anchor={key} data-endpoint-pin={letter}>
          <span className="fd-endpoint" aria-label={`Endpoint ${letter}`}>{letter}</span>
        </div>
      ))}
      {pins.map(({ key, anchor, reason, number, dimmed, route }) => (
        <div className="fd-pin-position" key={number} data-pin-anchor={anchor} data-dimmed={dimmed}
          data-interface-question={route || undefined}>
          <button className="fd-pin" type="button" data-question-number={number}
            aria-label={`Open question ${number}`} title={questionText(reason)} onClick={() => onSelect(key, number)}><span>{number}</span></button>
        </div>
      ))}
      {endpoints.length > 0 && (
        <div className="fd-route-position" data-route-label="">
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
  const [manifest, setManifest] = useState(FALLBACK_MANIFEST);
  const { compare, focus, tour } = manifest;
  const { base, target } = compare ?? FIELDDECK_COMPARE;
  const comparisonEnabled = Boolean(compare);
  const focusPart = focus?.part_id;
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
  const peek = useRef(null);
  const [peekMore, setPeekMore] = useState(0);
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
    fetchSceneManifest("cyberdeck-real-trial-20261020", controller.signal).then((result) => {
      if (!controller.signal.aborted && result?.schema === "hardware_splicer.scene_manifest.v1") {
        setManifest(result);
      }
    }).catch(() => {});
    return () => controller.abort();
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
  const sceneCompare = useMemo(() => comparisonEnabled ? { base, target } : null,
    [base, target, comparisonEnabled]);
  const index = useMemo(() => indexFielddeck(sidecars, sceneCompare), [sidecars, sceneCompare]);
  const rows = useMemo(() => rowsForMode(index, view.mode, sceneCompare), [index, view.mode, sceneCompare]);
  const selection = index.byKey.get(view.selected);
  const revision = view.mode === "compare" ? target : view.mode;
  const allQuestions = useMemo(() => openQuestions(sidecars, index), [sidecars, index]);
  const displayedKeys = useMemo(() => new Set(rows.map(({ key }) => key)), [rows]);
  const questions = useMemo(() => allQuestions.flatMap(({ keys, ...question }) => {
    const matching = [...keys].filter((key) => view.mode === "compare" || key.startsWith(`${revision}:`));
    if (!matching.length) return [];
    // An older revision's check can still be inspected from its visible counterpart.
    const visible = matching.filter((key) => displayedKeys.has(key));
    const fallback = view.mode === "compare" ? matching[0].replace(`${base}:`, `${target}:`) : matching[0];
    const key = visible[0] ?? (displayedKeys.has(fallback) ? fallback : matching[0]);
    return [{ ...question, key }];
  }), [allQuestions, displayedKeys, revision, view.mode, base, target]);
  const selectionQuestions = useMemo(() => {
    if (!selection) return [];
    const keys = selection.part
      ? [target, base].map((rev) => index.byPart.get(`${rev}:${selection.part.part_id}`)?.key)
      : view.mode === "compare" ? [selection.key, selection.key.replace(`${target}:`, `${base}:`)] : [selection.key];
    return allQuestions.flatMap((question) => !keys.some((key) => question.keys.has(key)) ? [] : [{
      ...question,
      scope: question.keys.has(selection.key) ? nameOf(selection)
        : `${[...question.keys][0].split(":")[0]}-inch revision`,
    }]);
  }, [allQuestions, index, selection, view.mode, base, target]);
  const treeOpen = narrow ? sheet === "parts" || sheet === "blockers" : desktopTreeOpen;
  const inspectorOpen = !narrow || sheet === "details";
  const selectedKeys = useMemo(() => selectedPartKeys(index, selection), [index, selection]);
  const oldKey = ghostDeltaKey(index, view.mode, selection, sceneCompare);
  const treeEndpoints = selection?.link ? [["A", selection.link.from_part_id], ["B", selection.link.to_part_id]]
    .map(([letter, id]) => [letter, index.byPart.get(`${selection.revision}:${id}`)?.key]) : [];
  const endpoints = view.faceView ? [] : treeEndpoints;
  const labels = view.faceView || narrow && selection?.link ? [] : rows.flatMap((row) => {
    if (!row.part || !linked.has(row.key)
      || !(selection ? selectedKeys.includes(row.key) : row.part.part_id === focusPart)) return [];
    const endpoint = endpoints.find(([, key]) => key === row.key)?.[0];
    const caption = row.delta === "removed" && view.mode === "compare" ? `${nameOf(row)} · removed` : undefined;
    return [{ ...row, endpoint, caption }];
  });
  if (!view.faceView && oldKey && linked.has(oldKey)) {
    labels.push({ key: oldKey, delta: "removed", caption: `${selection.part.label} · old revision` });
  }
  const pins = [];
  if (view.blockers && view.faceView) {
    for (const question of allQuestions) {
      const anchors = [...question.keys].filter((key) => index.byKey.get(key)?.part?.part_id === focusPart && linked.has(key));
      if (anchors.length) pins.push({ ...question, key: index.byPart.get(`${revision}:${focusPart}`)?.key ?? anchors[0], anchor: anchors[0] });
    }
  } else if (view.blockers) {
    if (selection?.link && !narrow) {
      for (const question of selectionQuestions) pins.push({ ...question, key: selection.key, route: true, dimmed: false });
    }
    for (const question of questions) {
      const { key } = question;
      if (linked.has(key) && displayedKeys.has(key)) pins.push({ ...question, anchor: key, dimmed: Boolean(selection?.link) });
    }
  }
  const comparisonAvailable = comparisonEnabled && sidecars[target]?.revision_diff?.status === "available";
  const comparisonRenderable = comparisonAvailable
    && [base, target].every((rev) => [...linked].some((key) => key.startsWith(`${rev}:`)));
  const faceAvailable = comparisonRenderable && focusPart
    && [base, target].every((rev) => linked.has(index.byPart.get(`${rev}:${focusPart}`)?.key));

  useLayoutEffect(() => {
    const panel = peek.current;
    if (!narrow || !selection?.link) {
      setPeekMore(0);
      return;
    }
    panel.scrollTop = 0;
    const update = () => {
      const bottom = panel.getBoundingClientRect().bottom;
      const items = [...panel.querySelectorAll("[data-peek-question]")].map((item) => item.getBoundingClientRect());
      const clipped = countClippedItems(items, { top: -Infinity, bottom });
      setPeekMore(clipped ? countClippedItems(items, { top: -Infinity, bottom: bottom - 24 }) : 0);
    };
    update();
    panel.addEventListener("scroll", update);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(panel);
    return () => {
      panel.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [narrow, selection, selectionQuestions]);

  function finishIntro() {
    setView((old) => ({
      ...old, mode: "compare", explode: DEFAULT_EXPLODE, hero: null, blockers: true,
      selected: index.byPart.get(`${target}:${focusPart}`)?.key ?? null,
    }));
  }

  function select(key, question = null) {
    setView((old) => ({
      ...old, selected: key, question, cue: null, hero: null, touring: false, blockers: true,
      faceView: old.faceView && !index.byKey.get(key)?.link,
    }));
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
        }, { base, target, focusPart });
        stage.current = runtime;
        setLinked(runtime.linked);
      } catch (error) {
        setStageError(`3D stage unavailable (${error.message}).`);
      }
    }
    const hasRevision = (rev) => [...(runtime?.linked ?? [])].some((key) => key.startsWith(`${rev}:`));
    const canPlay = comparisonAvailable && hasRevision(base) && hasRevision(target);
    if (canPlay && !introSeen && !current.current.reduced) {
      introSeen = true;
      setView({ ...INITIAL, mode: "compare", hero: performance.now(), blockers: false });
    } else if (canPlay) {
      introSeen = true;
      current.current.finishIntro();
    } else {
      const mode = hasRevision(target) || !hasRevision(base) && sidecars[target] ? target : base;
      setView({ ...INITIAL, mode, selected: index.byPart.get(`${mode}:${focusPart}`)?.key ?? null });
    }
    return () => {
      stage.current = null;
      runtime?.dispose();
    };
  }, [assets, index, sidecars, comparisonAvailable, base, target, focusPart]);

  useLayoutEffect(() => {
    stage.current?.update({
      mode: view.mode, explode: view.explode, explodeMotion, heroStart: view.hero,
      selectedKeys, cameraCue: view.cue, reduced, faceView: view.faceView,
      ghostDeltaKey: oldKey, selectedKey: selection?.key,
    });
  }, [assets, view, selectedKeys, reduced, explodeMotion, treeOpen, inspectorOpen, narrow, blockersOnly, sheet, keyOpen, moreOpen, oldKey, selection]);

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
      const rev = mode === "compare" ? target : mode;
      const key = active?.part ? index.byPart.get(`${rev}:${active.part.part_id}`)?.key
        : active?.link ? `${rev}:link:${active.link.interface_id}` : null;
      return { ...old, mode, question: null, selected: index.byKey.has(key) ? key : null, cue: null, touring: false, blockers: true };
    });
  }

  function goTo(stopIndex, touring = false) {
    const stop = tour[stopIndex];
    if (!stop) return;
    setMoreOpen(false);
    setExplodeMotion(null);
    setView((old) => {
      const showCompare = comparisonAvailable && (comparisonRenderable || !rendered);
      const mode = stop.revision === "compare" ? (showCompare ? "compare" : old.mode)
        : (sidecars[stop.revision] ? stop.revision : old.mode);
      const rev = mode === "compare" ? target : mode;
      const selected = stop.select ? index.byPart.get(`${rev}:${stop.select}`)
        ?? index.byKey.get(`${rev}:link:${stop.select}`)
        ?? rowsForMode(index, mode, sceneCompare).find((row) => row.part?.part_id === stop.select)
        : stop.diff && rowsForMode(index, mode, sceneCompare).find((row) => row.part && row.delta === stop.diff);
      return {
        ...old, mode, explode: stop.explode, hero: null,
        stop: stopIndex, question: null, faceView: false, selected: selected?.key ?? null, touring,
        cue: { stopIndex }, blockers: true,
      };
    });
  }

  useEffect(() => {
    if (!view.touring) return undefined;
    const next = view.stop + 1;
    const timer = window.setTimeout(() => {
      if (next < tour.length) goTo(next, true);
      else setView((old) => ({ ...old, touring: false }));
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [view.cue, view.touring, view.stop, rendered, index, comparisonAvailable, comparisonRenderable, tour, sceneCompare, sidecars, target]);

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

  const offsetLabel = view.explode > 0 ? `Presentation offset · ${Math.round(view.explode * 100)}%` : null;
  const toggleFace = () => {
    setView((old) => ({ ...old, faceView: !old.faceView, touring: false }));
    setMoreOpen(false);
  };

  return (
    <section className="fd-scene fielddeck-route" aria-labelledby="fd-title" data-testid="fielddeck-scene"
      data-scene-status={playing ? "hero" : modelVisible ? "settled" : loading ? "loading" : "unavailable"}>
      <div className="fd-stage" data-has-selection={Boolean(selection)} ref={host} tabIndex={0} aria-label="Fielddeck stage">
        <header className="fd-header">
          <div>
            {onExit && <button className="fd-exit" type="button" aria-label="Back to home" onClick={onExit}>←</button>}
            <h1 id="fd-title">{manifest.title}</h1>
            {!narrow && <span className="fd-revision">{manifest.subtitle}</span>}
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
            <PartTree rows={rows} view={view} endpoints={treeEndpoints} linked={linked} onSelect={select}
              questions={questions} blockersOnly={filtered} counts={view.mode === "compare" ? sidecars[target]?.revision_diff?.counts : null} />
          </div>
        </aside>
        <Inspector row={selection} index={index} questions={selectionQuestions} open={inspectorOpen} />

        {!modelVisible && <div className="fd-stage-message" role="status">
          {loading ? "Loading Fielddeck models…" : errors.join(" ") || "Fielddeck model unavailable."}
        </div>}
        {modelVisible && errors.length > 0 && <p className="fd-stage-warning" role="status">{errors.join(" ")}</p>}
        {playing && <button className="fd-skip" type="button" onClick={finishIntro}>Skip intro</button>}

        <Annotations labels={labels} selection={view.faceView ? null : selection} endpoints={endpoints}
          pins={pins} faceView={view.faceView} base={base} target={target} onSelect={select} />
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
                  <label htmlFor="fd-explode">{offsetLabel ?? "Explode"}</label>
                  <input id="fd-explode" aria-label="Explode" type="range" min="0" max="1" step="0.01" value={view.explode}
                    onChange={(event) => {
                      setExplodeMotion(null);
                      setView((old) => ({ ...old, explode: Number(event.target.value), cue: null, touring: false, blockers: true }));
                    }} />
                  {!offsetLabel && <output htmlFor="fd-explode">0%</output>}
                  {!narrow && <button type="button" onClick={() => {
                    setView((old) => ({ ...old, touring: false, blockers: true }));
                    setExplodeMotion({ from: view.explode, to: view.explode > 0 ? 0 : 1, start: performance.now() });
                  }}>{view.explode > 0 ? "Collapse" : "Explode view"}</button>}
                </div>}
                {faceAvailable && <button type="button" title={focus.label} onClick={toggleFace}>
                  {view.faceView ? "Back to 3D" : "Face view"}
                </button>}
                {narrow && <button type="button" aria-expanded={keyOpen} aria-controls="fd-legend"
                  onClick={() => setKeyOpen(!keyOpen)}>Key</button>}
                {tour.length > 0 && <div className="fd-tour" role="group" aria-label="Tour">
                  <button type="button" disabled={!view.stop} onClick={() => goTo(view.stop - 1)}
                    aria-label="Previous stop">←</button>
                  <strong>{(tour[view.stop] ?? tour[0]).label}</strong>
                  <button type="button" disabled={view.stop === tour.length - 1} onClick={() => goTo(view.stop + 1)}
                    aria-label="Next stop">→</button>
                  <button type="button" onClick={() => view.touring
                    ? setView((old) => ({ ...old, touring: false }))
                    : goTo(0, !reduced)}>{view.touring ? "Pause tour" : "Start tour"}</button>
                </div>}
              </div>
            </div>
          )}
          {narrow && offsetLabel && (modelVisible || playing) && <div className="fd-offset-caption">{offsetLabel}</div>}
        </div>
        {narrow && faceAvailable && <button className="fd-face-pill" type="button" title={focus.label} onClick={toggleFace}>
          {view.faceView ? "Back to 3D" : "Face view"}
        </button>}
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
          <div className="fd-peek" ref={peek} data-has-more={peekMore > 0}>
            <strong>{nameOf(selection) ?? "Select a part or interface"}</strong>
            {selection && <span className="fd-status">{statusOf(selection)}</span>}
            {selection?.link && <Endpoints row={selection} index={index} />}
            {(selection?.link ? selectionQuestions : selectionQuestions.slice(0, 1)).map(({ number, reason, scope }) => (
              <span key={number} data-peek-question="">
                <QuestionNumber number={number} /> {questionText(reason)}
                {!selection?.link && scope !== nameOf(selection) && <small className="fd-revision-tag">{scope}</small>}
              </span>
            ))}
            <div className="fd-peek-spacer" aria-hidden="true" />
          </div>
          {peekMore > 0 && <div className="fd-inspector-more fd-peek-more"><span>+{peekMore} more</span></div>}
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
