import { NextResponse } from "next/server";
import {
  forwardUiJsonResponse,
  getVisionApiBaseUrl,
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
  const apiBaseUrl = getVisionApiBaseUrl();
  const target = `${apiBaseUrl}/analyze`;
  const inbound = await request.formData();
  const file = inbound.get("file");

  if (!isFileLike(file)) {
    return NextResponse.json({ error: "file required" }, { status: 400 });
  }

  const outbound = new FormData();
  outbound.set("file", file, file.name);

  for (const field of ["backend", "enable_ocr", "enable_quality_assessment", "reference_counts", "reference_topology", "aoi_profile"]) {
    const value = inbound.get(field);
    if (typeof value === "string" && value.trim()) {
      outbound.set(field, value);
    }
  }

  for (const field of ["golden_file", "reference_topology_file"]) {
    const value = inbound.get(field);
    if (isFileLike(value)) {
      outbound.set(field, value, value.name);
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
