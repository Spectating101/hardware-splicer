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
    type?: string;
  };
}

interface ErrorBody {
  detail?: string | ErrorDetail;
}

export interface ProjectReviewApiError extends Error {
  status?: number;
  type?: string;
}

export type ProjectReviewStatus = "pending" | "accepting" | (string & {});

export type ProjectReviewDecisionValue = "accepted" | "rejected" | (string & {});

export type ProjectReviewFlagSeverity = "required" | (string & {});

export interface ProjectRevisionEntry {
  revision: number;
  current_stage: string;
  review_id?: string | null;
  review_actor?: string | null;
}

export interface ListProjectRevisionsResponse {
  revisions?: ProjectRevisionEntry[];
}

export interface ProjectReviewFlag {
  code: string;
  severity: ProjectReviewFlagSeverity;
  message: string;
  object_id?: string | null;
  path?: string | null;
  collection?: string;
}

export interface ProjectReviewObjectChange {
  collection: string;
  object_id: string;
  change_type: string;
  field_changes?: unknown[];
  review_flags?: ProjectReviewFlag[];
}

export interface ProjectReviewDiff {
  review_flags?: ProjectReviewFlag[];
  object_changes?: ProjectReviewObjectChange[];
}

export interface ProjectReviewChangeSummary {
  added?: number;
  removed?: number;
  modified?: number;
  snapshot_fields_changed?: number;
}

export interface ProjectReviewSnapshotChange {
  path: string;
}

export interface ProjectReviewDecisionRecord {
  actor?: string | null;
  decided_at?: string | null;
  accepted_revision?: number | null;
}

export interface ProjectReviewSummary {
  review_id: string;
  status: ProjectReviewStatus;
  base_revision: number;
  created_by: string;
  note?: string | null;
}

export interface ProjectReviewDetail extends ProjectReviewSummary {
  created_at?: string | null;
  review_flags?: ProjectReviewFlag[];
  diff?: ProjectReviewDiff | null;
  summary?: ProjectReviewChangeSummary | null;
  snapshot_changes?: ProjectReviewSnapshotChange[];
  decision?: ProjectReviewDecisionRecord | null;
}

export interface ListProjectReviewsResponse {
  reviews?: ProjectReviewSummary[];
}

export interface ProjectReviewResponse {
  review?: ProjectReviewDetail | null;
}

export interface DecideProjectReviewInput {
  decision: ProjectReviewDecisionValue;
  actor: string;
  note?: string;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as ProjectReviewApiError;
    error.status = res.status;
    error.type = (detail as ErrorDetail | undefined)?.type || (detail as ErrorDetail | undefined)?.error?.type || "request_failed";
    throw error;
  }
  return body as T;
}

export async function listProjectRevisions(projectId: string): Promise<ListProjectRevisionsResponse> {
  return parseJson<ListProjectRevisionsResponse>(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/revisions`),
  );
}

export async function listProjectReviews(projectId: string): Promise<ListProjectReviewsResponse> {
  return parseJson<ListProjectReviewsResponse>(
    await fetch(`${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews`),
  );
}

export async function loadProjectReview(
  projectId: string,
  reviewId: string,
): Promise<ProjectReviewResponse> {
  return parseJson<ProjectReviewResponse>(
    await fetch(
      `${API_BASE}/v1/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}`,
    ),
  );
}

export async function decideProjectReview(
  projectId: string,
  reviewId: string,
  { decision, actor, note = "" }: DecideProjectReviewInput,
): Promise<ProjectReviewResponse> {
  return parseJson<ProjectReviewResponse>(
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
