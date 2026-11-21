const API_BASE: string =
  import.meta.env.VITE_API_BASE !== undefined
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? "/api"
      : "";

interface ErrorDetail {
  message?: string;
  error?: {
    message?: string;
  };
}

interface ErrorBody {
  detail?: string | ErrorDetail;
}

export type EngineeringReviewStatusValue =
  | "blocked"
  | "review_required"
  | "partial"
  | "failed"
  | "clear"
  | (string & {});

export type EngineeringReviewSeverity =
  | "blocker"
  | "warning"
  | "advisory"
  | "info"
  | (string & {});

export interface EngineeringReviewAdapterSetup {
  instruction?: string;
}

export interface EngineeringReviewAdapter {
  available?: boolean;
  name?: string;
  authority_ceiling?: string;
  setup?: EngineeringReviewAdapterSetup;
}

export interface EngineeringReviewInputItem {
  analyzer_type?: string;
}

export interface EngineeringReviewSummary {
  status?: EngineeringReviewStatusValue;
  headline: string;
  blocker_count?: number;
  warning_count?: number;
  analysis_count?: number;
  provenance_coverage_pct?: number | null;
}

export interface EngineeringReviewFinding {
  finding_id: string;
  rule_id: string;
  title: string;
  analyzer_type: string;
  severity?: EngineeringReviewSeverity;
  recommendation?: string;
  confidence?: string;
  components?: string[];
  nets?: string[];
}

export interface EngineeringReviewFailure {
  analyzer_type: string;
  reason: string;
  detail: string;
}

export interface EngineeringReviewResult {
  skipped?: boolean;
  reason?: string;
  cached?: boolean;
  summary?: EngineeringReviewSummary | null;
  findings?: EngineeringReviewFinding[];
  failures?: EngineeringReviewFailure[];
}

export interface EngineeringReviewStatusResponse {
  can_run?: boolean;
  adapter?: EngineeringReviewAdapter;
  supported_inputs?: string[];
  inputs?: EngineeringReviewInputItem[];
  latest_review?: EngineeringReviewResult | null;
}

export interface RunEngineeringReviewOptions {
  force?: boolean;
  timeoutS?: number;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.error?.message || detail?.message || res.statusText;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return body as T;
}

export async function fetchEngineeringReviewStatus(
  buildDir: string,
): Promise<EngineeringReviewStatusResponse> {
  const res = await fetch(`${API_BASE}/v1/build-files/engineering-review/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ build_dir: buildDir }),
  });
  return parseJson<EngineeringReviewStatusResponse>(res);
}

export async function runEngineeringReview(
  buildDir: string,
  { force = false, timeoutS = 180 }: RunEngineeringReviewOptions = {},
): Promise<EngineeringReviewResult> {
  const res = await fetch(`${API_BASE}/v1/build-files/engineering-review/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      build_dir: buildDir,
      force,
      timeout_s: timeoutS,
    }),
  });
  return parseJson<EngineeringReviewResult>(res);
}
