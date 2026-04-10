import { NextResponse } from "next/server";
import { getCircuitApiBaseUrl, getProxyAuthHeaders } from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ filename: string }> }) {
  const apiBaseUrl = getCircuitApiBaseUrl();

  const { filename } = await ctx.params;
  if (!filename) return NextResponse.json({ error: "filename required" }, { status: 400 });

  const url = `${apiBaseUrl}/api/v2/manufacture/download-gerber/${encodeURIComponent(filename)}`;
  const authHeaders = getProxyAuthHeaders(_req);
  try {
    const res = await fetch(url, { method: "GET", headers: authHeaders });
    const body = await res.arrayBuffer();

    const headers = new Headers();
    headers.set("content-type", res.headers.get("content-type") || "application/zip");
    headers.set("content-disposition", res.headers.get("content-disposition") || `attachment; filename=\"${filename}\"`);

    return new NextResponse(body, { status: res.status, headers });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Could not reach ${url}. ${message}` },
      { status: 502 },
    );
  }
}
