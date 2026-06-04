import {
  forwardUiJsonResponse,
  getProxyAuthHeaders,
  getVisionApiBaseUrl,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const inbound = new URL(request.url);
  const target = new URL(`${getVisionApiBaseUrl()}/hardware/production-casefile/run`);
  const liveModelAdvisory = inbound.searchParams.get("live_model_advisory");
  if (liveModelAdvisory) target.searchParams.set("live_model_advisory", liveModelAdvisory);
  const body = await request.text();

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...getProxyAuthHeaders(request),
      },
      body,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target.toString());
  } catch (error: unknown) {
    return proxyUiFailureResponse(target.toString(), error);
  }
}
