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
