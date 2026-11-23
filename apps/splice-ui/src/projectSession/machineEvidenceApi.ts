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

export interface MachineEvidenceApiError extends Error {
  status?: number;
  type?: string;
}

export interface RecordMachineEvidenceInput {
  evidence: Record<string, unknown>;
  verification?: Record<string, unknown> | null;
  promotions?: ReadonlyArray<Record<string, unknown>>;
}

export interface RecordMachineEvidenceResponse {
  project: Record<string, unknown>;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as MachineEvidenceApiError;
    error.status = res.status;
    error.type = (detail as ErrorDetail | undefined)?.type || "request_failed";
    throw error;
  }
  return body as T;
}

export async function recordMachineEvidence(
  project: Record<string, unknown>,
  { evidence, verification = null, promotions = [] }: RecordMachineEvidenceInput,
): Promise<RecordMachineEvidenceResponse> {
  return parseJson<RecordMachineEvidenceResponse>(
    await fetch(`${API_BASE}/v1/machine-projects/record-evidence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, evidence, verification, promotions }),
    }),
  );
}
