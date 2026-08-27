import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string; packageId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { projectId, packageId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/engineering-packages/${encodeURIComponent(packageId)}/download`;

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });
    if (!response.ok) {
      return await forwardUiJsonResponse(response, target);
    }
    const headers = new Headers();
    for (const name of [
      "content-type",
      "content-length",
      "content-disposition",
      "x-hardware-splicer-package-id",
      "x-hardware-splicer-package-sha256",
      "x-hardware-splicer-source-revision",
    ]) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("cache-control", "no-store");
    return new Response(response.body, {
      status: response.status,
      headers,
    });
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
