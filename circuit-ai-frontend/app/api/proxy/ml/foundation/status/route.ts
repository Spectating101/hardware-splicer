import {
  forwardUiJsonResponse,
  getCircuitApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const target = new URL(`${getCircuitApiBaseUrl()}/ml/foundation/status`);

  for (const field of ["device_hint", "goal", "has_video"]) {
    const value = url.searchParams.get(field);
    if (value) {
      target.searchParams.set(field, value);
    }
  }

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });

    return await forwardUiJsonResponse(response, target.toString());
  } catch (error: unknown) {
    return proxyUiFailureResponse(target.toString(), error);
  }
}
