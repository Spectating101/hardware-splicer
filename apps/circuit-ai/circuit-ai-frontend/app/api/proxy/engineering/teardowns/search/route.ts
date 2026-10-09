import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Finds iFixit teardown links for a device name. Read-only. */
export async function GET(request: Request) {
  const query = new URL(request.url).searchParams.get("q") ?? "";
  const target = `${getHardwareSplicerApiUrl()}/v1/teardowns/search?q=${encodeURIComponent(query.slice(0, 200))}`;
  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
