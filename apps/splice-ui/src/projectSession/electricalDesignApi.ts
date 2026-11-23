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

export interface ElectricalDesignApiError extends Error {
  status?: number;
  type?: string;
}

export interface ElectricalDesignPin {
  pin_id: string;
  component_id: string;
  name: string;
  number: string;
  net_id?: string | null;
  [key: string]: unknown;
}

export interface ElectricalDesignNet {
  net_id: string;
  name: string;
  kind: string;
  pin_ids?: string[];
  authority: string;
  unresolved_fields?: string[];
  [key: string]: unknown;
}

export interface ElectricalDesign {
  components?: unknown[];
  pins?: ElectricalDesignPin[];
  nets?: ElectricalDesignNet[];
  [key: string]: unknown;
}

export interface ElectricalErcIssue {
  code: string;
  severity: string;
  object_id?: string | null;
  message: string;
}

export interface ElectricalErcReport {
  error_count?: number;
  warning_count?: number;
  issues?: ElectricalErcIssue[];
}

export interface ElectricalDesignResponse {
  design?: ElectricalDesign | null;
  erc?: ElectricalErcReport | null;
}

async function parseJson<T>(res: Response): Promise<T> {
  const body = (await res.json().catch(() => ({}))) as unknown;
  if (!res.ok) {
    const detail = (body as ErrorBody | null | undefined)?.detail;
    const error = new Error(
      typeof detail === "string"
        ? detail
        : detail?.message || detail?.error?.message || res.statusText || `Request failed (${res.status})`,
    ) as ElectricalDesignApiError;
    error.status = res.status;
    error.type = (detail as ErrorDetail | undefined)?.type || "request_failed";
    throw error;
  }
  return body as T;
}

export async function projectElectricalDesign(
  project: Record<string, unknown>,
): Promise<ElectricalDesignResponse> {
  return parseJson<ElectricalDesignResponse>(
    await fetch(`${API_BASE}/v1/electrical-designs/from-machine-project`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project }),
    }),
  );
}

export async function editElectricalDesign(
  design: ElectricalDesign | Record<string, unknown>,
  operations: ReadonlyArray<Record<string, unknown>>,
): Promise<ElectricalDesignResponse> {
  return parseJson<ElectricalDesignResponse>(
    await fetch(`${API_BASE}/v1/electrical-designs/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ design, operations }),
    }),
  );
}

export async function checkElectricalDesign(
  design: ElectricalDesign | Record<string, unknown>,
): Promise<ElectricalDesignResponse> {
  return parseJson<ElectricalDesignResponse>(
    await fetch(`${API_BASE}/v1/electrical-designs/erc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ design }),
    }),
  );
}
