const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

async function parseJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.error?.message || detail?.message || res.statusText;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return body;
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return parseJson(res);
}

export async function fetchModuleCatalog() {
  const res = await fetch(`${API_BASE}/v1/modules/catalog`);
  return parseJson(res);
}

export async function fetchExamples() {
  const res = await fetch(`${API_BASE}/v1/examples/splice-intakes`);
  return parseJson(res);
}

export async function fetchDonorFixtures() {
  const res = await fetch(`${API_BASE}/v1/examples/donor-fixtures`);
  return parseJson(res);
}

export async function clarifyIntent(intent) {
  const res = await fetch(`${API_BASE}/v1/intent/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent }),
  });
  return parseJson(res);
}

export async function spliceAndBuild(intake, { exportGerber = false, outDir = null } = {}) {
  const res = await fetch(`${API_BASE}/v1/splice-and-build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intake,
      export_gerber: exportGerber,
      ...(outDir ? { out_dir: outDir } : {}),
    }),
  });
  return parseJson(res);
}

export async function submitSpliceJob(intake, { exportGerber = false, requestId = null } = {}) {
  const res = await fetch(`${API_BASE}/v1/jobs/splice-build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      intake,
      export_gerber: exportGerber,
      ...(requestId ? { request_id: requestId } : {}),
    }),
  });
  return parseJson(res);
}

export async function fetchJobs({ status = null, limit = 20 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  const res = await fetch(`${API_BASE}/v1/jobs?${params}`);
  return parseJson(res);
}

export async function fetchJob(jobId) {
  const res = await fetch(`${API_BASE}/v1/jobs/${encodeURIComponent(jobId)}`);
  return parseJson(res);
}

export async function fetchJobResult(jobId) {
  const res = await fetch(`${API_BASE}/v1/jobs/${encodeURIComponent(jobId)}/result`);
  return parseJson(res);
}

export function jobBundleUrl(jobId) {
  const base = API_BASE || "";
  return `${base}/v1/jobs/${encodeURIComponent(jobId)}/bundle`;
}

export async function benchStatus(buildDir) {
  const res = await fetch(`${API_BASE}/v1/splice-bench/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function benchSubmit(buildDir, measurements) {
  const res = await fetch(`${API_BASE}/v1/splice-bench/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, measurements }),
  });
  return parseJson(res);
}

export async function benchCaptureTemplate(buildDir) {
  const res = await fetch(`${API_BASE}/v1/splice-bench/capture-template`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function benchSubmitCapture(buildDir, capture) {
  const res = await fetch(`${API_BASE}/v1/splice-bench/submit-capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, capture }),
  });
  return parseJson(res);
}

export async function composeBuild(payload) {
  const res = await fetch(`${API_BASE}/v1/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_gerber: false,
      ...payload,
    }),
  });
  return parseJson(res);
}

export async function composeAgentLoop(
  payload,
  { maxManualRetries = 2, finalizePackage = false, projectName = null } = {},
) {
  const res = await fetch(`${API_BASE}/v1/compose/agent-loop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      export_gerber: false,
      max_manual_retries: maxManualRetries,
      finalize_package: finalizePackage,
      ...(projectName ? { project_name: projectName } : {}),
      ...payload,
    }),
  });
  return parseJson(res);
}

export async function renderProjectPackage(buildDir, { source = "compose" } = {}) {
  const res = await fetch(`${API_BASE}/v1/project-package/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, source }),
  });
  return parseJson(res);
}

export async function submitComposeJob(payload, { exportGerber = false, requestId = null } = {}) {
  const res = await fetch(`${API_BASE}/v1/jobs/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      export_gerber: exportGerber,
      ...(requestId ? { request_id: requestId } : {}),
    }),
  });
  return parseJson(res);
}

export async function composePhrase(
  phrase,
  { allowLlmFirst = false, exportGerber = false, wireOnly = false, moduleIds = null } = {},
) {
  const res = await fetch(`${API_BASE}/v1/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phrase,
      allow_llm_first: allowLlmFirst,
      export_gerber: exportGerber,
      wire_only: wireOnly,
      ...(moduleIds ? { module_ids: moduleIds } : {}),
    }),
  });
  return parseJson(res);
}

export async function listBuildFiles(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/list`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function fetchBuildFileContent(buildDir, relative) {
  const res = await fetch(`${API_BASE}/v1/build-files/content`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, relative }),
  });
  return parseJson(res);
}

export async function fetchDesignQuality(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/design-quality`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function fetchIntegrationsCatalog() {
  const res = await fetch(`${API_BASE}/v1/integrations/catalog`);
  return parseJson(res);
}

export async function listBuildArtifacts(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/artifacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function exportCircuitJson(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/circuit-json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function downloadBuildArtifact(buildDir, relative) {
  const res = await fetch(`${API_BASE}/v1/build-files/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, relative }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message || body?.detail || res.statusText);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = relative.split("/").pop() || "artifact";
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function runBuildAutoroute(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/autoroute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, confirm: true }),
  });
  return parseJson(res);
}

export async function fetchBuildBom(buildDir, { enrich = false } = {}) {
  const res = await fetch(`${API_BASE}/v1/build-files/bom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir, enrich }),
  });
  return parseJson(res);
}

export async function fetchFabManifest(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/fab-manifest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function exportBuildViews(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/export-views`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function recheckBuildAfterKicad(buildDir, { refreshPackage = true, exportViews = true } = {}) {
  const res = await fetch(`${API_BASE}/v1/build-files/recheck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      build_dir: buildDir,
      refresh_package: refreshPackage,
      export_views: exportViews,
    }),
  });
  return parseJson(res);
}

export async function composeCanvas(nodes, wires, { wireOnly = false, exportGerber = false } = {}) {
  const res = await fetch(`${API_BASE}/v1/compose-canvas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nodes,
      wires,
      wire_only: wireOnly,
      export_gerber: exportGerber,
    }),
  });
  return parseJson(res);
}

export async function netlistCompile({ circuitJson, netlist, kicadNetlistText, buildId = "generic_low_voltage_build", exportGerber = false } = {}) {
  const res = await fetch(`${API_BASE}/v1/netlist-compile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(circuitJson ? { circuit_json: circuitJson } : {}),
      ...(netlist ? { netlist } : {}),
      ...(kicadNetlistText ? { kicad_netlist_text: kicadNetlistText } : {}),
      build_id: buildId,
      export_gerber: exportGerber,
    }),
  });
  return parseJson(res);
}

export async function fetchNetlistFixtures() {
  const res = await fetch(`${API_BASE}/v1/examples/netlist-fixtures`);
  return parseJson(res);
}

export async function fetchNetlistFixture(fixtureId) {
  const res = await fetch(`${API_BASE}/v1/examples/netlist-fixtures/${encodeURIComponent(fixtureId)}`);
  return parseJson(res);
}

export async function fetchVisionCapabilities() {
  const res = await fetch(`${API_BASE}/v1/vision/capabilities`);
  return parseJson(res);
}

export async function visionEnrichIntake(intake, { apply = true, live = false } = {}) {
  const res = await fetch(`${API_BASE}/v1/vision/enrich-intake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intake, apply, live }),
  });
  return parseJson(res);
}

export async function donorBoardVision(intake) {
  const res = await fetch(`${API_BASE}/v1/donor-board-vision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intake }),
  });
  return parseJson(res);
}
