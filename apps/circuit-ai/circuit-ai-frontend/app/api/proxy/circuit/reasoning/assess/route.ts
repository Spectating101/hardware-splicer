import {
  forwardUiJsonResponse,
  getProxyAuthHeaders,
  getVisionApiBaseUrl,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(request: Request) {
  const target = `${getVisionApiBaseUrl()}/circuit/reasoning/assess`;
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
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
