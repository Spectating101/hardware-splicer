import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ exampleId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { exampleId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/devices/examples/${encodeURIComponent(exampleId)}/plan`;
  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
