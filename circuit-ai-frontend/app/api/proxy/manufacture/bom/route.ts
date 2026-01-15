import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const apiBaseUrl = process.env.CIRCUIT_AI_API_URL || "http://localhost:5000";
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";

  const inbound = await req.formData();
  const file = inbound.get("netlist_file");
  const includePricing = inbound.get("include_pricing");
  const format = inbound.get("format");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "netlist_file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("netlist_file", file, file.name);
  if (typeof includePricing === "string") outbound.set("include_pricing", includePricing);
  if (typeof format === "string") outbound.set("format", format);

  const headers: HeadersInit = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
  const res = await fetch(`${apiBaseUrl}/api/v2/manufacture/bom`, {
    method: "POST",
    body: outbound,
    headers,
  });

  const contentType = res.headers.get("content-type") || "application/octet-stream";
  const body = await res.arrayBuffer();
  return new NextResponse(body, { status: res.status, headers: { "content-type": contentType } });
}
