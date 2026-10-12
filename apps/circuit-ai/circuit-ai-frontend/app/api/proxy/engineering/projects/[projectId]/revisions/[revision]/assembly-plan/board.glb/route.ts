import {
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; revision: string }>;
};

/** Streams the binary model through untouched; the JSON proxy helper would corrupt it. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId, revision } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/revisions/${encodeURIComponent(revision)}/assembly-plan/board.glb`;
  const conditional = request.headers.get("if-none-match");

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: { ...getProxyAuthHeaders(request), ...(conditional ? { "if-none-match": conditional } : {}) },
      cache: "no-store",
    });
    const headers = new Headers();
    for (const name of ["content-type", "etag", "cache-control", "content-length"]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.status === 304 ? null : response.body, { status: response.status, headers });
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
