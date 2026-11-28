/** Data for the workbench: HS's toolbelt, the outside-tool registry, the spine and the measured records. */
const API_BASE = import.meta.env.VITE_API_BASE !== undefined
  ? import.meta.env.VITE_API_BASE
  : import.meta.env.DEV ? "/api" : "";

async function getJson(path, init) {
  const res = await fetch(`${API_BASE}${path}`, init);
  let body = null;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : `${res.status} ${res.statusText}`;
    throw new Error(detail);
  }
  return body;
}

export const fetchTools = (signal) => getJson("/v1/toolbelt/tools", { signal });
export const fetchSpine = (signal) => getJson("/v1/bench/spine", { signal });
export const fetchMeasures = (signal) => getJson("/v1/bench/measures", { signal });
export const renderUrl = (name) => `${API_BASE}/v1/bench/renders/${encodeURIComponent(name)}`;

/** The registry is itself a toolbelt tool, so the screen reads it the same way an agent does. */
export async function fetchOutsideTools(signal) {
  const env = await runTool("hs_external_tools", {}, signal);
  return env?.result?.tools ?? [];
}

export function runTool(name, args, signal) {
  return getJson(`/v1/toolbelt/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(args ?? {}),
    signal,
  });
}
