import { NextResponse } from "next/server";
import { getCircuitApiBaseUrl, getProxyAuthHeaders } from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Real physics-engine DFM preflight. /api/v2/* is the canonical Flask surface.
export async function POST(req: Request) {
  const apiBaseUrl = getCircuitApiBaseUrl();

  const inbound = await req.formData();
  const file = inbound.get("pcb_file");
  const hints = inbound.get("hints");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "pcb_file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("pcb_file", file, file.name);
  if (typeof hints === "string" && hints.trim()) outbound.set("hints", hints);

  const headers = getProxyAuthHeaders(req);
  try {
    const res = await fetch(`${apiBaseUrl}/api/v2/report/dfm`, {
      method: "POST",
      body: outbound,
      headers,
    });
    const text = await res.text();
    try {
      return NextResponse.json(JSON.parse(text), { status: res.status });
    } catch {
      return new NextResponse(text, {
        status: res.status,
        headers: { "content-type": "text/plain" },
      });
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Could not reach ${apiBaseUrl}/api/v2/report/dfm. ${message}` },
      { status: 502 },
    );
  }
}
