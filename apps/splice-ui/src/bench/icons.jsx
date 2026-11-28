/** One drawn icon set: 16 px grid, 1.5 stroke, round caps. */
const PATHS = {
  spine: "M3 4h3M10 4h3M3 12h3M10 12h3M6 4h4M6 12h4M8 4v8",
  tool: "M10.5 2.5a3 3 0 0 0-3.9 3.9L2.5 10.5l3 3 4.1-4.1a3 3 0 0 0 3.9-3.9l-1.8 1.8-1.7-.4-.4-1.7z",
  plug: "M6 2v3M10 2v3M4.5 5h7v2.5a3.5 3.5 0 0 1-7 0zM8 11v3",
  chevron: "M6 4l4 4-4 4",
  search: "M7 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM14 14l-3.5-3.5",
  play: "M5 3.5v9l7-4.5z",
  board: "M2.5 3.5h11v9h-11zM5 6.5h2M9 6.5h2M5 9.5h6",
  chart: "M3 13V3M3 13h10M6 10V8M9 10V5M12 10V7",
  result: "M3.5 2.5h6l3 3v8h-9zM9.5 2.5v3h3M5.5 8.5h5M5.5 11h3",
  console: "M2.5 3.5h11v9h-11zM5 7l2 1.5L5 10M8.5 10.5H11",
  external: "M9 3h4v4M13 3L7.5 8.5M11 9.5v3.5H3V5h3.5",
  close: "M4 4l8 8M12 4l-8 8",
  gate: "M3 13V5l5-2.5L13 5v8M6 13V9h4v4",
  layers: "M8 2.5l5.5 3L8 8.5 2.5 5.5zM2.5 8.5l5.5 3 5.5-3M2.5 11l5.5 3 5.5-3",
};

export function Icon({ name, size = 16, className = "" }) {
  return (
    <svg className={`bi ${className}`} width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} fill={name === "play" ? "currentColor" : "none"} />
    </svg>
  );
}

/** Run outcome mark. Filled = the record shows a result; hollow = not run; dashed = not recorded. */
export function Outcome({ outcome, size = 10 }) {
  const r = size / 2 - 1;
  const c = size / 2;
  const dashed = outcome === "unknown";
  const hollow = outcome === "not_run" || dashed;
  return (
    <svg className={`wb-outcome is-${outcome}`} width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={c} cy={c} r={r} fill={hollow ? "none" : "currentColor"} stroke="currentColor" strokeWidth="1.5"
        strokeDasharray={dashed ? "2 1.6" : undefined} />
    </svg>
  );
}
