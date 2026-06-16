import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  proxyUiFailureResponse,
} from "../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const target = `${getHardwareSplicerApiUrl()}/v1/compose`;
  const body = await request.text();

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      cache: "no-store",
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
