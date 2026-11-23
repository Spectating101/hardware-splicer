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

export interface BenchCaptureEvidenceApiError extends Error {
  status?: number;
  type?: string;
}

export interface BenchCaptureWarning {
  code: string;
  measurement?: string | null;
  message: string;
}

export interface BenchCaptureProjectionSummary {
  capture_id?: string;
  capture_sha256: string;
  imported_count: number;
  measurement_count: number;
  warnings?: BenchCaptureWarning[];
}

export interface ProjectBenchCaptureEvidenceResponse {
  project: Record<string, unknown>;
  bench_capture?: BenchCaptureProjectionSummary | null;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as BenchCaptureEvidenceApiError;
    error.status = res.status;
    error.type = (detail as ErrorDetail | undefined)?.type || "request_failed";
    throw error;
  }
  return body as T;
}

export async function projectBenchCaptureEvidence(
  project: Record<string, unknown>,
  capture: Record<string, unknown>,
  targetMap: Record<string, unknown> = {},
): Promise<ProjectBenchCaptureEvidenceResponse> {
  return parseJson<ProjectBenchCaptureEvidenceResponse>(
    await fetch(`${API_BASE}/v1/machine-projects/from-bench-capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project,
        capture,
        target_map: targetMap,
      }),
    }),
  );
}
