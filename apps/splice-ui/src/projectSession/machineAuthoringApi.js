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
    error.type = detail?.type || "request_failed";
    throw error;
  }
  return body;
}

export async function editMachineProject(project, operations) {
  return parseJson(
    await fetch(`${API_BASE}/v1/machine-projects/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, operations }),
    }),
  );
}

export async function stageMachineProjectReview(
  projectId,
  candidateSnapshot,
  { baseRevision, createdBy = "workspace-author", note = "" } = {},
) {
  return parseJson(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_snapshot: candidateSnapshot,
        base_revision: baseRevision,
        created_by: createdBy,
        note,
      }),
    }),
  );
}
