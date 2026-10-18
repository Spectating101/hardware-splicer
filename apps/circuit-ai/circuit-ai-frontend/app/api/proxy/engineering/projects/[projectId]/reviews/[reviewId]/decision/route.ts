import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; reviewId: string }> };

/** Decides a staged review. The operator token travels in its own header; for a design staged from a mission the
 * backend takes the decider from it and refuses without a verified person. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, reviewId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/reviews/${encodeURIComponent(reviewId)}/decision`;
  const token = request.headers.get("x-hs-operator-token");
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: { "content-type": "application/json", ...getProxyAuthHeaders(request), ...(token ? { "x-hs-operator-token": token } : {}) },
      body: (await request.text()) || "{}",
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
