import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; revision: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { projectId, revision } = await context.params;
  const enrich = new URL(request.url).searchParams.get("enrich") === "true" ? "true" : "false";
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/revisions/${encodeURIComponent(revision)}/parts?enrich=${enrich}`;

  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
