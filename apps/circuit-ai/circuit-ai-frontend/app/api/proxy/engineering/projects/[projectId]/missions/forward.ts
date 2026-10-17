import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../_backend";

/** Forwarded untouched so the backend can verify the operator; never logged or stored here. */
export function operatorTokenHeader(request: Request): Record<string, string> {
  const token = request.headers.get("x-hs-operator-token");
  return token ? { "x-hs-operator-token": token } : {};
}

/** The mission routes on the canonical backend, for one project and optionally one mission. */
export function missionTarget(projectId: string, rest = "") {
  return `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/missions${rest}`;
}

/**
 * Forward one mission call. JSON answers go through the shared proxy handling (upstream errors become
 * `{ok:false}` payloads); a ZIP package is streamed back as it is.
 */
export async function forwardMission(request: Request, target: string, method: "GET" | "POST", body?: string) {
  try {
    const response = await fetch(target, {
      method,
      headers: {
        ...(method === "POST" ? { "content-type": "application/json" } : {}),
        ...getProxyAuthHeaders(request),
        ...operatorTokenHeader(request),
      },
      body: method === "POST" ? body ?? "{}" : undefined,
      cache: "no-store",
    });
    if (response.ok && (response.headers.get("content-type") || "").includes("application/zip")) {
      const headers = new Headers();
      for (const name of ["content-type", "content-length", "content-disposition"]) {
        const value = response.headers.get(name);
        if (value) headers.set(name, value);
      }
      headers.set("cache-control", "no-store");
      return new Response(response.body, { status: response.status, headers });
    }
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}

