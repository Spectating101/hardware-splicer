import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isDiscoveryIndex(uri: string) {
  try {
    const url = new URL(uri);
    const hostname = url.hostname.toLowerCase();
    if ((hostname === "youtube.com" || hostname.endsWith(".youtube.com")) && url.pathname === "/results") {
      return true;
    }
    if ((hostname === "google.com" || hostname.endsWith(".google.com")) && url.pathname.startsWith("/search")) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

function normalizeDiscoverySources(body: string) {
  const parsed: unknown = JSON.parse(body);
  if (!isRecord(parsed) || !Array.isArray(parsed.engineering_sources)) return body;

  const engineeringSources = parsed.engineering_sources.map((value) => {
    if (!isRecord(value)) return value;
    const uri = typeof value.uri === "string" ? value.uri : typeof value.url === "string" ? value.url : "";
    if (!uri || !isDiscoveryIndex(uri)) return value;
    const metadata = isRecord(value.metadata) ? value.metadata : {};
    return {
      ...value,
      source_type: "other",
      authority_ceiling: "declared",
      claims: [],
      metadata: {
        ...metadata,
        discovery_only: true,
        requires_concrete_source_selection: true,
        requires_timestamp_range_for_media_observation: true,
        original_source_type: value.source_type,
        original_authority_ceiling: value.authority_ceiling,
      },
    };
  });

  return JSON.stringify({ ...parsed, engineering_sources: engineeringSources });
}

export async function POST(request: Request) {
  const target = `${getHardwareSplicerApiUrl()}/v1/engineering/plan`;

  try {
    const requestBody = await request.text();
    const body = normalizeDiscoverySources(requestBody);
    const response = await fetch(target, {
      method: "POST",
      headers: {
        ...getProxyAuthHeaders(request),
        "content-type": "application/json",
      },
      body,
      cache: "no-store",
    });

    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
