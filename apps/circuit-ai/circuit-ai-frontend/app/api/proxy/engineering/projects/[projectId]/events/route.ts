import { getHardwareSplicerApiUrl, getProxyAuthHeaders, proxyUiFailureResponse } from "../../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ projectId: string }>;
};

/** Passes the server-sent event stream through unchanged; the JSON proxy helper would buffer it. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  const target = `${getHardwareSplicerApiUrl()}/v1/projects/${encodeURIComponent(projectId)}/events`;

  try {
    const upstream = await fetch(target, {
      method: "GET",
      headers: { ...getProxyAuthHeaders(request), accept: "text/event-stream" },
      cache: "no-store",
      signal: request.signal,
    });
    if (!upstream.ok || !upstream.body) {
      return new Response(JSON.stringify({ ok: false, error: `The event stream is unavailable (${upstream.status}).`, status: upstream.status }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response(upstream.body, {
      status: 200,
      headers: {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-cache, no-transform",
        connection: "keep-alive",
        "x-accel-buffering": "no",
      },
    });
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
