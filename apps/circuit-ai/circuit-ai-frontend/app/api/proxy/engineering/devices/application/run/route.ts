import { forwardUiJsonResponse, getHardwareSplicerApiUrl, getHardwareSplicerExecutionAuthHeaders, proxyUiFailureResponse } from '../../../../_backend';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const MAX_BODY_BYTES = 64 * 1024;

export async function POST(request: Request) {
  const target = `${getHardwareSplicerApiUrl()}/v1/devices/application/run`;
  try {
    const declared = Number(request.headers.get('content-length') ?? 0);
    const tooLarge = () => Response.json({ ok: false, error: 'The request may be at most 65536 bytes.' }, { status: 413 });
    if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return tooLarge();
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) { await reader.cancel(); return tooLarge(); }
      chunks.push(value);
    }
    const body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    const response = await fetch(target, {
      method: 'POST', headers: { 'content-type': 'application/json', ...getHardwareSplicerExecutionAuthHeaders(request) },
      body, cache: 'no-store', signal: request.signal,
    });
    return forwardUiJsonResponse(response, target);
  } catch (error) {
    return proxyUiFailureResponse(target, error);
  }
}
