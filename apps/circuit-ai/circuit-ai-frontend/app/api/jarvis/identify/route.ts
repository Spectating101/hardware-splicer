// Vision identification endpoint. Accepts multipart/form-data with a single
// "image" field OR JSON { imageBase64, mediaType }. Returns structured
// component list + safety level. Cached by perceptual hash.

import { callJarvis, extractJson, type JarvisMessage } from "@/lib/jarvis/client";
import { cacheGet, cacheSet, hashBuffer } from "@/lib/cache/component-cache";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

export const runtime = "nodejs";
export const maxDuration = 60;

interface IdentifyResult {
  safety_level: SafetyLevel;
  explanation: string;
  components: Array<Partial<SalvageModule> & { id: string; label: string; kind: string }>;
  fromCache?: boolean;
  model?: string;
}

async function readImage(req: Request): Promise<{ buf: Buffer; mediaType: string } | null> {
  const ct = req.headers.get("content-type") ?? "";

  if (ct.startsWith("multipart/form-data")) {
    const fd = await req.formData();
    const file = fd.get("image");
    if (!(file instanceof Blob)) return null;
    const buf = Buffer.from(await file.arrayBuffer());
    const mediaType = file.type || "image/jpeg";
    return { buf, mediaType };
  }

  if (ct.includes("application/json")) {
    const json = await req.json() as { imageBase64?: string; mediaType?: string };
    if (!json.imageBase64) return null;
    const cleaned = json.imageBase64.replace(/^data:[^,]+,/, "");
    return { buf: Buffer.from(cleaned, "base64"), mediaType: json.mediaType ?? "image/jpeg" };
  }

  return null;
}

export async function POST(req: Request) {
  const img = await readImage(req);
  if (!img) {
    return Response.json({ error: "Missing image (multipart 'image' field or JSON imageBase64)" }, { status: 400 });
  }

  const key = hashBuffer(img.buf);
  const cached = await cacheGet<IdentifyResult>("identify", key);
  if (cached) {
    return Response.json({ ...cached.value, fromCache: true, model: cached.model });
  }

  const messages: JarvisMessage[] = [{
    role: "user",
    content: [
      { type: "image", source: { type: "base64", media_type: img.mediaType, data: img.buf.toString("base64") } },
      { type: "text", text: "Identify every visible component or functional block on this board. Output the JSON described in the system prompt." },
    ],
  }];

  try {
    const result = await callJarvis({ flow: "identify", messages, maxTokens: 2500 });
    const parsed = extractJson<IdentifyResult>(result.text);
    if (!parsed) {
      return Response.json({
        error: "Model output was not valid JSON",
        raw: result.text.slice(0, 500),
        model: result.model,
      }, { status: 502 });
    }
    await cacheSet("identify", key, parsed, result.model);
    return Response.json({ ...parsed, fromCache: false, model: result.model });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
