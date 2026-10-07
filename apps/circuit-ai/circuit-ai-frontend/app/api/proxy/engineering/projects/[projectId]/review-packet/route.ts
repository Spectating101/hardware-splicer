import {
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

/** The review packet, passed through untouched so the file name and the bytes the backend hashed reach the browser. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const query = new URL(request.url).search;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/review-packet${query}`;

  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    const headers = new Headers();
    for (const name of ["content-type", "content-disposition", "cache-control"]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers });
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
