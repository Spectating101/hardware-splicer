import {
  forwardUiJsonResponse,
  getHardwareSplicerApiUrl,
  getProxyAuthHeaders,
  proxyUiFailureResponse,
} from "../../../_backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BODY_BYTES = 64 * 1024;

function tooLarge() {
  return Response.json({ ok: false, error: `The spec may be at most ${MAX_BODY_BYTES} bytes.`, status: 413 }, { status: 413 });
}

/** Reads the body a piece at a time and gives up as soon as it is too big, so an oversized upload is never held whole. */
async function readLimited(request: Request): Promise<string | null> {
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const joined = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(joined);
}

/** Reviews a device plan. Nothing is kept: the backend returns the review and forgets it. */
export async function POST(request: Request) {
  const target = `${getHardwareSplicerApiUrl()}/v1/devices/engineering`;
  try {
    const body = await readLimited(request);
    if (body === null) return tooLarge();
    const response = await fetch(target, {
      method: "POST",
      headers: { "content-type": "application/json", ...getProxyAuthHeaders(request) },
      body,
      cache: "no-store",
      signal: request.signal,
    });
    return await forwardUiJsonResponse(response, target);
  } catch (error: unknown) {
    return proxyUiFailureResponse(target, error);
  }
}
