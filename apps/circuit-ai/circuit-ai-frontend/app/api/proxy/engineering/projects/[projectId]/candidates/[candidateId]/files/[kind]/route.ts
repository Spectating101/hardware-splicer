import {
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; candidateId: string; kind: string }>;
};

/** The proposed KiCad file as text. Passed through unparsed so the viewer sees exactly what the backend hashed. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId, candidateId, kind } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/candidates/${encodeURIComponent(candidateId)}/files/${encodeURIComponent(kind)}`;

  try {
    const response = await fetch(target, { method: "GET", headers: getProxyAuthHeaders(request), cache: "no-store" });
    const headers = new Headers();
    for (const name of ["content-type", "etag", "content-length"]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers });
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
