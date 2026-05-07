import {
  forwardUiJsonResponse,
  getCircuitApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  const target = `${getCircuitApiBaseUrl()}/board-sessions/${encodeURIComponent(sessionId)}/dossier`;

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
