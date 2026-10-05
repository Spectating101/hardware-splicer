import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../../_backend";

/** Forwarded untouched so the backend can verify the operator; never logged or stored here. */
function operatorTokenHeader(request: Request): Record<string, string> {
  const token = request.headers.get("x-hs-operator-token");
  return token ? { "x-hs-operator-token": token } : {};
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

async function forward(request: Request, context: RouteContext, method: "GET" | "POST") {
  const { projectId } = await context.params;
  const incoming = new URL(request.url);
  const query = incoming.search;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/threads${query}`;

  try {
    const response = await fetch(target, {
      method,
      headers: {
        ...(method === "POST" ? { "content-type": "application/json" } : {}),
        ...getProxyAuthHeaders(request),
        ...operatorTokenHeader(request),
      },
      body: method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}

export async function GET(request: Request, context: RouteContext) {
  return forward(request, context, "GET");
}

export async function POST(request: Request, context: RouteContext) {
  return forward(request, context, "POST");
}
