import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const apiBaseUrl = process.env.CIRCUIT_AI_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";

  const inbound = await req.formData();
  const file = inbound.get("pcb_file");
  const quantity = inbound.get("quantity");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "pcb_file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("pcb_file", file, file.name);
  if (typeof quantity === "string") outbound.set("quantity", quantity);

  const headers: HeadersInit = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
  try {
    const res = await fetch(`${apiBaseUrl}/api/v2/manufacture/gerber`, {
      method: "POST",
      body: outbound,
      headers,
    });

    const text = await res.text();
    try {
      const json = JSON.parse(text);
      return NextResponse.json(json, { status: res.status });
    } catch {
      return new NextResponse(text, { status: res.status, headers: { "content-type": "text/plain" } });
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Could not reach ${apiBaseUrl}/api/v2/manufacture/gerber. ${message}` },
      { status: 502 },
    );
  }
}
