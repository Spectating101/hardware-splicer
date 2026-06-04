import {
  forwardUiJsonResponse,
  getVisionApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  const target = `${getVisionApiBaseUrl()}/board-sessions/${encodeURIComponent(sessionId)}/captures`;
  const formData = await request.formData();

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: getProxyAuthHeaders(request),
      body: formData,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
