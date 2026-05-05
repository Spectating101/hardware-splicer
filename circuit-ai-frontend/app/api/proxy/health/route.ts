import { NextResponse } from "next/server";
import { getCircuitApiBaseUrl, getProxyAuthHeaders } from "../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const apiBaseUrl = getCircuitApiBaseUrl();
  const target = `${apiBaseUrl}/healthz`;
  try {
    const headers = getProxyAuthHeaders();
    const res = await fetch(target, { method: "GET", headers });
    const text = await res.text();

    if (!res.ok) {
      let error = `Health check returned ${res.status}.`;
      try {
        const json = JSON.parse(text) as { detail?: string; error?: string; message?: string };
        error = json.error || json.detail || json.message || error;
      } catch {
        if (text.trim()) error = text.trim();
      }

      return NextResponse.json({
        ok: false,
        status: "unhealthy",
        error,
        target,
        timestamp: new Date().toISOString(),
      });
    }

    try {
      const json = JSON.parse(text);
      return NextResponse.json({ timestamp: new Date().toISOString(), ...json });
    } catch {
      return NextResponse.json({ ok: true, status: "healthy", detail: text, target, timestamp: new Date().toISOString() });
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    const detail = message === "fetch failed"
      ? `Could not reach ${target}. Start the backend or set CIRCUIT_AI_API_URL.`
      : `Health check failed for ${target}: ${message}`;
    return NextResponse.json(
      { ok: false, status: "unhealthy", error: detail, target, timestamp: new Date().toISOString() },
    );
  }
}
