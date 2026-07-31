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

export async function fetchEngineeringReviewStatus(buildDir) {
  const res = await fetch(`${API_BASE}/v1/build-files/engineering-review/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson(res);
}

export async function runEngineeringReview(buildDir, { force = false, timeoutS = 180 } = {}) {
  const res = await fetch(`${API_BASE}/v1/build-files/engineering-review/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      build_dir: buildDir,
      force,
      timeout_s: timeoutS,
    }),
  });
  return parseJson(res);
}
