import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../_backend";

/** The mission routes on the canonical backend, for one project and optionally one mission. */
export function missionTarget(projectId: string, rest = "") {
  return `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/missions${rest}`;
}

/**
 * Forward one read-only mission call. GET only: this proxy cannot open, accept, answer, run, stage or build
 * a mission, and it never forwards an operator token, so it cannot act as a person.
 */
export async function forwardMission(request: Request, target: string, method: "GET") {
  try {
    const response = await fetch(target, {
      method,
      headers: { ...getProxyAuthHeaders(request) },
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
