const API_BASE: string =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

interface ErrorDetail {
  message?: string;
  type?: string;
  error?: {
    message?: string;
  };
}

interface ErrorBody {
  detail?: string | ErrorDetail;
}

export interface MachineAuthoringApiError extends Error {
  status?: number;
  type?: string;
}

export interface EditMachineProjectResponse {
  project: Record<string, unknown>;
}

export interface StageMachineProjectReviewOptions {
  baseRevision?: number;
  createdBy?: string;
  note?: string;
}

export interface StagedMachineProjectReview {
  review_id: string;
  base_revision: number;
}

export interface StageMachineProjectReviewResponse {
  review?: StagedMachineProjectReview | null;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as MachineAuthoringApiError;
    error.status = res.status;
    error.type = (detail as ErrorDetail | undefined)?.type || "request_failed";
    throw error;
  }
  return body as T;
}

export async function editMachineProject(
  project: Record<string, unknown>,
  operations: ReadonlyArray<Record<string, unknown>>,
): Promise<EditMachineProjectResponse> {
  return parseJson<EditMachineProjectResponse>(
    await fetch(`${API_BASE}/v1/machine-projects/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, operations }),
    }),
  );
}

export async function stageMachineProjectReview(
  projectId: string,
  candidateSnapshot: Record<string, unknown>,
  { baseRevision, createdBy = "workspace-author", note = "" }: StageMachineProjectReviewOptions = {},
): Promise<StageMachineProjectReviewResponse> {
  return parseJson<StageMachineProjectReviewResponse>(
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
