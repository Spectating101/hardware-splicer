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
  const inbound = new URL(request.url).searchParams;
  const marking = inbound.get("marking") ?? "";
  const pkg = inbound.get("package") ?? "";
  const query = new URLSearchParams({ marking: marking.slice(0, 200) });
  if (pkg) query.set("package", pkg.slice(0, 200));
  const target = `${getHardwareSplicerApiUrl()}/v1/parts/lookup?${query.toString()}`;
  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
