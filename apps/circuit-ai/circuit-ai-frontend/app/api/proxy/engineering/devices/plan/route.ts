import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Plans a device from a spec. Nothing is kept: the backend returns the proposal and forgets it. */
export async function POST(request: Request) {
  const target = `${getHardwareSplicerApiUrl()}/v1/devices/plan`;
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: { "content-type": "application/json", ...getProxyAuthHeaders(request) },
      body: await request.text(),
      cache: "no-store",
      signal: request.signal,
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
