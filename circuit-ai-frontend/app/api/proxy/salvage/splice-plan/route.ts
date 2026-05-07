import {
  forwardUiJsonResponse,
  getCircuitApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const inbound = new URL(request.url);
  const target = new URL(`${getCircuitApiBaseUrl()}/salvage/splice-plan`);
  const commitSession = inbound.searchParams.get("commit_session");
  if (commitSession) target.searchParams.set("commit_session", commitSession);
  const body = await request.text();

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...getProxyAuthHeaders(request),
      },
      body,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target.toString());
  } catch (error: unknown) {
    return proxyUiFailureResponse(target.toString(), error);
  }
}
