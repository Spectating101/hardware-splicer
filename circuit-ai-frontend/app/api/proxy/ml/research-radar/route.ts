import {
  forwardUiJsonResponse,
  getVisionApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const target = `${getVisionApiBaseUrl()}/ml/research-radar`;

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });

    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
