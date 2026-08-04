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

type StreamingRequestInit = RequestInit & { duplex: "half" };

export async function POST(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/sources/ingest-file`;
  const contentType = request.headers.get("content-type");

  if (!contentType?.toLowerCase().startsWith("multipart/form-data")) {
    return Response.json(
      {
        ok: false,
        error: "multipart/form-data with a boundary is required",
        target,
      },
      { status: 415 },
    );
  }
  if (!request.body) {
    return Response.json(
      { ok: false, error: "multipart request body is required", target },
      { status: 400 },
    );
  }

  try {
    const init: StreamingRequestInit = {
      method: "POST",
      headers: {
        ...getProxyAuthHeaders(request),
        "content-type": contentType,
      },
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
