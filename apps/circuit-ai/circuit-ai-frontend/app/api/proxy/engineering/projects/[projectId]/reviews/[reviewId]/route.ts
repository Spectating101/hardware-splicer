import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; reviewId: string }> };

/** Reads one staged review: its status and what accepting it would change. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId, reviewId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}`;
  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
