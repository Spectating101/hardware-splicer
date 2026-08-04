export type ProxyErrorPayload = {
  ok?: boolean;
  detail?: string;
  error?: string;
  status?: number;
  target?: string;
};

export async function readJsonPayload<T>(response: Response): Promise<T | null> {
  try {
    return await response.json() as T;
  } catch {
    return null;
  }
}

export function getProxyErrorMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") return fallback;
  const value = payload as ProxyErrorPayload;
  const detail = value.error || value.detail;
  return typeof detail === "string" && detail.trim() ? detail : fallback;
}

export function isProxyFailure(payload: unknown): payload is ProxyErrorPayload {
  return Boolean(payload) && typeof payload === "object" && (payload as ProxyErrorPayload).ok === false;
}
