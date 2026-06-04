import { NextResponse } from "next/server";
import { getProxyAuthHeaders, getVisionApiBaseUrl } from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const target = `${getVisionApiBaseUrl()}/health`;

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });
    const text = await response.text();
    const payload = parseJsonObject(text);

    if (!response.ok) {
      return NextResponse.json(
        {
          ok: false,
          status: "unhealthy",
          error: healthError(payload, text, `Vision health check returned ${response.status}.`),
          target,
          timestamp: new Date().toISOString(),
        },
        { status: response.status },
      );
    }

    const healthy = payload.ok === true || payload.status === "healthy";

    return NextResponse.json({
      ok: healthy,
      target,
      timestamp: new Date().toISOString(),
      ...payload,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    const detail = message === "fetch failed"
      ? `Could not reach ${target}. Start the FastAPI backend or set CIRCUIT_AI_VISION_URL.`
      : `Vision health check failed for ${target}: ${message}`;

    return NextResponse.json({ ok: false, status: "unhealthy", error: detail, target, timestamp: new Date().toISOString() }, { status: 502 });
  }
}

function parseJsonObject(text: string): Record<string, unknown> {
  try {
    const payload = JSON.parse(text) as unknown;
    return payload && typeof payload === "object" && !Array.isArray(payload) ? payload as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function healthError(payload: Record<string, unknown>, text: string, fallback: string) {
  for (const key of ["error", "detail", "message"]) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return text.trim() || fallback;
}
