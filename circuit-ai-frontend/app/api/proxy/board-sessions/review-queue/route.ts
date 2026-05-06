import {
  forwardUiJsonResponse,
  getCircuitApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const inbound = new URL(request.url);
  const target = new URL(`${getCircuitApiBaseUrl()}/board-sessions/review-queue`);
  for (const key of ["status", "limit"]) {
    const value = inbound.searchParams.get(key);
    if (value) target.searchParams.set(key, value);
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
