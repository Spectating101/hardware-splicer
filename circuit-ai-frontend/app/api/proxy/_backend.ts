import { NextResponse } from "next/server";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getCircuitApiBaseUrl() {
  return process.env.CIRCUIT_AI_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_BASE_URL;
}

export function getProxyAuthHeaders(request?: Request): HeadersInit {
  const forwardedAuthorization = request?.headers.get("authorization");
  if (forwardedAuthorization) {
    return { Authorization: forwardedAuthorization };
  }

  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";
  return apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
}

function extractErrorMessage(text: string, fallback: string) {
  try {
    const payload = JSON.parse(text) as { detail?: string; error?: string; message?: string };
    const detail = payload.error || payload.detail || payload.message;
    return typeof detail === "string" && detail.trim() ? detail : fallback;
  } catch {
    return text.trim() ? text.trim() : fallback;
  }
}

export async function forwardJsonResponse(response: Response) {
  const text = await response.text();

  try {
    return NextResponse.json(JSON.parse(text), { status: response.status });
  } catch {
    return new NextResponse(text, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") || "text/plain" },
    });
  }
}

export async function forwardUiJsonResponse(response: Response, target: string) {
  const text = await response.text();

  if (!response.ok) {
    return NextResponse.json({
      ok: false,
      error: extractErrorMessage(text, `Upstream request failed for ${target} (${response.status}).`),
      status: response.status,
      target,
    });
  }

  try {
    return NextResponse.json(JSON.parse(text));
  } catch {
    return NextResponse.json({ ok: true, raw: text, target });
  }
}

export function proxyFailureResponse(target: string, error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  const detail = message === "fetch failed"
    ? `Could not reach ${target}. Start the backend or set CIRCUIT_AI_API_URL.`
    : `Proxy request failed for ${target}: ${message}`;

  return NextResponse.json({ error: detail, target }, { status: 502 });
}

export function proxyUiFailureResponse(target: string, error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  const detail = message === "fetch failed"
    ? `Could not reach ${target}. Start the backend or set CIRCUIT_AI_API_URL.`
    : `Proxy request failed for ${target}: ${message}`;

  return NextResponse.json({ ok: false, error: detail, target });
}
