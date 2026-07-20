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
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    );
    error.status = res.status;
    error.type = detail?.type || detail?.error?.type || "request_failed";
    throw error;
  }
  return body;
}

export async function listProjectRevisions(projectId) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/revisions`),
  );
}

export async function listProjectReviews(projectId) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews`),
  );
}

export async function loadProjectReview(projectId, reviewId) {
  return parseJson(
    await fetch(
      `${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}`,
    ),
  );
}

export async function decideProjectReview(projectId, reviewId, { decision, actor, note = "" }) {
  return parseJson(
    await fetch(
      `${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, actor, note }),
      },
    ),
  );
}
