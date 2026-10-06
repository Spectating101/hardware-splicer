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

async function forward(request: Request, context: RouteContext, method: "GET" | "POST") {
  const { projectId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/presence`;
  const operatorToken = request.headers.get("x-hs-operator-token");

  try {
    const response = await fetch(target, {
      method,
      headers: {
        ...(method === "POST" ? { "content-type": "application/json" } : {}),
        ...getProxyAuthHeaders(request),
        ...(operatorToken ? { "x-hs-operator-token": operatorToken } : {}),
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
