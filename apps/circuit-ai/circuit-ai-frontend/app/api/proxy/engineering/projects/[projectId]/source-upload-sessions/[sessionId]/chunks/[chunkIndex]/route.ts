import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    projectId: string;
    sessionId: string;
    chunkIndex: string;
  }>;
};

type StreamingRequestInit = RequestInit & { duplex: "half" };

export async function PUT(request: Request, context: RouteContext) {
  const { projectId, sessionId, chunkIndex } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/source-upload-sessions/${encodeURIComponent(sessionId)}/chunks/${encodeURIComponent(chunkIndex)}`;
  if (!request.body) {
    return Response.json(
      { ok: false, error: "chunk request body is required", target },
      { status: 400 },
    );
  }
  try {
    const headers: Record<string, string> = {
      ...getProxyAuthHeaders(request),
      "content-type": request.headers.get("content-type") || "application/octet-stream",
    };
    const chunkHash = request.headers.get("x-chunk-sha256");
    if (chunkHash) headers["x-chunk-sha256"] = chunkHash;
    const init: StreamingRequestInit = {
      method: "PUT",
      headers,
      body: request.body,
      duplex: "half",
      cache: "no-store",
    };
    const response = await fetch(target, init);
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
