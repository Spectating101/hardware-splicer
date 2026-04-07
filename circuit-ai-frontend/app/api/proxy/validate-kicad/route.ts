import { NextResponse } from "next/server";
import { forwardUiJsonResponse, proxyUiFailureResponse } from "../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function isFileLike(value: FormDataEntryValue | null): value is File {
  return Boolean(
    value
    && typeof value === "object"
    && "arrayBuffer" in value
    && "name" in value
    && typeof value.name === "string",
  );
}

export async function POST(req: Request) {
  const apiBaseUrl = process.env.CIRCUIT_AI_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const apiKey = process.env.CIRCUIT_AI_API_KEY || "";

  const inbound = await req.formData();
  const file = inbound.get("kicad_file");
  const hints = inbound.get("hints");

  if (!isFileLike(file)) {
    return NextResponse.json({ error: "kicad_file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("kicad_file", file, file.name);
  if (typeof hints === "string" && hints.trim()) outbound.set("hints", hints);

  const headers: HeadersInit = apiKey ? { Authorization: `Bearer ${apiKey}` } : {};
  try {
    const res = await fetch(`${apiBaseUrl}/api/v2/workflow/validate-kicad`, {
      method: "POST",
      body: outbound,
      headers,
    });

    return await forwardUiJsonResponse(res, `${apiBaseUrl}/api/v2/workflow/validate-kicad`);
  } catch (error: unknown) {
    return proxyUiFailureResponse(`${apiBaseUrl}/api/v2/workflow/validate-kicad`, error);
  }
}
