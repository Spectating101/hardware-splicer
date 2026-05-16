import {
  forwardUiJsonResponse,
  getVisionApiBaseUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const inbound = new URL(request.url);
  const target = new URL(`${getVisionApiBaseUrl()}/repair/value-trials`);
  const limit = inbound.searchParams.get("limit");
  if (limit) target.searchParams.set("limit", limit);

  try {
    const response = await fetch(target, {
      method: "GET",
      headers: getProxyAuthHeaders(request),
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target.toString());
  } catch (error: unknown) {
    return proxyUiFailureResponse(target.toString(), error);
  }
}

export async function POST(request: Request) {
  const target = `${getVisionApiBaseUrl()}/repair/value-trials`;
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
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
