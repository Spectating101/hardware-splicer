import { NextResponse } from "next/server";
import {
  forwardUiJsonResponse,
  getCircuitApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../_backend";

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

export async function POST(request: Request) {
  const apiBaseUrl = getCircuitApiBaseUrl();
  const target = `${apiBaseUrl}/analyze`;
  const inbound = await request.formData();
  const file = inbound.get("file");

  if (!isFileLike(file)) {
    return NextResponse.json({ error: "file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("file", file, file.name);

  for (const field of ["backend", "enable_ocr", "enable_quality_assessment"]) {
    const value = inbound.get(field);
    if (typeof value === "string" && value.trim()) {
      outbound.set(field, value);
    }
  }

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: getProxyAuthHeaders(request),
      body: outbound,
    });

    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
