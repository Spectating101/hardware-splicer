import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const apiBaseUrl = process.env.CIRCUIT_AI_API_URL || "http://localhost:5000";
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";

  const inbound = await req.formData();
  const file = inbound.get("kicad_file");
  const hints = inbound.get("hints");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "kicad_file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("kicad_file", file, file.name);
  if (typeof hints === "string" && hints.trim()) outbound.set("hints", hints);

  const headers: HeadersInit = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
  const res = await fetch(`${apiBaseUrl}/api/v2/workflow/validate-kicad`, {
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
}
