import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const requestUrl = new URL(request.url);
  const revision = requestUrl.searchParams.get("revision");
  const query = revision ? `?revision=${encodeURIComponent(revision)}` : "";
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/source-storage/audit${query}`;
  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
