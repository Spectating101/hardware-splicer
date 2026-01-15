import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const apiBaseUrl = process.env.CIRCUIT_AI_API_URL || "http://localhost:5000";
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";
  try {
    const headers: HeadersInit = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
    const res = await fetch(`${apiBaseUrl}/api/health`, { method: "GET", headers });
    const text = await res.text();
    try {
      const json = JSON.parse(text);
      return NextResponse.json(json, { status: res.status });
    } catch {
      return new NextResponse(text, { status: res.status, headers: { "content-type": "text/plain" } });
    }
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 502 });
  }
}
