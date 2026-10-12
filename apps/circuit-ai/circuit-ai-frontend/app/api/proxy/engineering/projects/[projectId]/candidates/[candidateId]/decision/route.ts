import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; candidateId: string }>;
};

/** Forwarded untouched so the backend can verify the operator; never logged or stored here. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, candidateId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/candidates/${encodeURIComponent(candidateId)}/decision`;
  const token = request.headers.get("x-hs-operator-token");

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...getProxyAuthHeaders(request),
        ...(token ? { "x-hs-operator-token": token } : {}),
      },
      body: await request.text(),
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
