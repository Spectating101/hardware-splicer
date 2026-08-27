import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; sessionId: string }>;
};

function targetFor(projectId: string, sessionId: string) {
  return `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/source-upload-sessions/${encodeURIComponent(sessionId)}`;
}

export async function GET(request: Request, context: RouteContext) {
  const { projectId, sessionId } = await context.params;
  const target = targetFor(projectId, sessionId);
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

export async function DELETE(request: Request, context: RouteContext) {
  const { projectId, sessionId } = await context.params;
  const target = targetFor(projectId, sessionId);
  try {
    const response = await fetch(target, {
      method: "DELETE",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
