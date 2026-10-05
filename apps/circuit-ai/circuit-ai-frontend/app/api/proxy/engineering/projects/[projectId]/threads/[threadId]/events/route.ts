import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; threadId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { projectId, threadId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(threadId)}/events`;

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...getProxyAuthHeaders(request),
        ...(request.headers.get("x-hs-operator-token") ? { "x-hs-operator-token": request.headers.get("x-hs-operator-token") as string } : {}),
      },
      body: await request.text(),
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
