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

/** A dry run: the backend returns what the edits would produce and keeps nothing. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/candidates/preview`;

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: { "content-type": "application/json", ...getProxyAuthHeaders(request) },
      body: await request.text(),
      cache: "no-store",
      signal: request.signal,
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
