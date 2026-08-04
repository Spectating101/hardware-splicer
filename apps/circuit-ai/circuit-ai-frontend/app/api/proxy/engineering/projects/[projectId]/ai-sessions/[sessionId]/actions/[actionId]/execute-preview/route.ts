import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    projectId: string;
    sessionId: string;
    actionId: string;
  }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { projectId, sessionId, actionId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/ai-sessions/${encodeURIComponent(sessionId)}/actions/${encodeURIComponent(actionId)}/execute-preview`;

  try {
    const body = await request.text();
    const response = await fetch(target, {
      method: "POST",
      headers: {
        ...getProxyAuthHeaders(request),
        "content-type": request.headers.get("content-type") || "application/json",
      },
      body,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
