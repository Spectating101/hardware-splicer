import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** Looks a marking up in the server's KiCad libraries. Read-only. */
export async function GET(request: Request) {
  const marking = new URL(request.url).searchParams.get("marking") ?? "";
  const target = `${getHardwareSplicerApiUrl()}/v1/parts/lookup?marking=${encodeURIComponent(marking.slice(0, 200))}`;
  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
