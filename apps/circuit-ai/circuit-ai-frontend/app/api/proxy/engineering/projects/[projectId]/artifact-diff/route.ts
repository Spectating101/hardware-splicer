import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const incoming = new URL(request.url);
  const query = new URLSearchParams();
  for (const key of ["base", "candidate", "kind"]) {
    const value = incoming.searchParams.get(key);
    if (value) query.set(key, value);
  }
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/artifact-diff?${query.toString()}`;

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
