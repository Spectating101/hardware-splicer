import { NextResponse } from "next/server";

// Two distinct backends. Flask api_server.py is the canonical surface
// (/api/health, /api/v2/*). The FastAPI app (src/api/v1/main.py) serves the
// vision/repair/board-session surface on bare paths (/analyze, /board-sessions,
// /repair/*, /salvage/*, /ml/*, /components, /educational, /projects, /healthz).
// They are separate processes on separate ports and must not be conflated.
const DEFAULT_FLASK_BASE_URL = "http://localhost:5000";
const DEFAULT_VISION_BASE_URL = "http://localhost:8000";

// Canonical Flask backend. Used by /api/v2/* and /api/health proxies.
export function getCircuitApiBaseUrl() {
  return process.env.CIRCUIT_AI_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_FLASK_BASE_URL;
}

// FastAPI vision/repair backend. Used by all bare-path proxies.
export function getVisionApiBaseUrl() {
  return (
    process.env.CIRCUIT_AI_VISION_URL ||
    process.env.NEXT_PUBLIC_VISION_API_URL ||
    DEFAULT_VISION_BASE_URL
  );
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
