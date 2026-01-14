import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ filename: string }> }) {
  const { filename } = await ctx.params;
  if (!filename) return NextResponse.json({ error: "filename required" }, { status: 400 });

  const url = `http://localhost:5000/api/v2/manufacture/download-gerber/${encodeURIComponent(filename)}`;
  const res = await fetch(url, { method: "GET" });
  const body = await res.arrayBuffer();

  const headers = new Headers();
  headers.set("content-type", res.headers.get("content-type") || "application/zip");
  headers.set("content-disposition", res.headers.get("content-disposition") || `attachment; filename="${filename}"`);

  return new NextResponse(body, { status: res.status, headers });
}

