// Salvage planner. Accepts multipart image + optional description, returns
// a list of reusable modules with extraction recipes.

import { callJarvis, extractJson, type JarvisMessage, type JarvisContent } from "@/lib/jarvis/client";
import { cacheGet, cacheSet, hashBuffer, hashString } from "@/lib/cache/component-cache";
import type { SafetyLevel, SalvageModule } from "@/lib/cad-types";

export const runtime = "nodejs";
export const maxDuration = 60;

interface SalvageResult {
  safety_level: SafetyLevel;
  explanation: string;
  modules: SalvageModule[];
  fromCache?: boolean;
  model?: string;
}

export async function POST(req: Request) {
  const ct = req.headers.get("content-type") ?? "";

  let imageBuf: Buffer | null = null;
  let mediaType = "image/jpeg";
  let description = "";

  if (ct.startsWith("multipart/form-data")) {
    const fd = await req.formData();
    const file = fd.get("image");
    if (file instanceof Blob) {
      imageBuf = Buffer.from(await file.arrayBuffer());
      mediaType = file.type || "image/jpeg";
    }
    description = (fd.get("description") as string) ?? "";
  } else if (ct.includes("application/json")) {
    const json = await req.json() as { imageBase64?: string; mediaType?: string; description?: string };
    if (json.imageBase64) {
      imageBuf = Buffer.from(json.imageBase64.replace(/^data:[^,]+,/, ""), "base64");
      mediaType = json.mediaType ?? "image/jpeg";
    }
    description = json.description ?? "";
  }

  if (!imageBuf && !description) {
    return Response.json({ error: "Need either image or description" }, { status: 400 });
  }

  const key = imageBuf
    ? `${hashBuffer(imageBuf)}_${hashString(description).slice(0, 8)}`
    : hashString(description);
  const cached = await cacheGet<SalvageResult>("salvage", key);
  if (cached) return Response.json({ ...cached.value, fromCache: true, model: cached.model });

  const content: JarvisContent[] = [];
  if (imageBuf) {
    content.push({ type: "image", source: { type: "base64", media_type: mediaType, data: imageBuf.toString("base64") } });
  }
  content.push({
    type: "text",
    text: `Plan the salvage for this device. ${description ? `User notes: ${description}` : ""} Output the JSON described in the system prompt.`,
  });

  const messages: JarvisMessage[] = [{ role: "user", content }];

  try {
    const result = await callJarvis({ flow: "salvage", messages, maxTokens: 3000 });
    const parsed = extractJson<SalvageResult>(result.text);
    if (!parsed) {
      return Response.json({ error: "Model output was not valid JSON", raw: result.text.slice(0, 500) }, { status: 502 });
    }
    await cacheSet("salvage", key, parsed, result.model);
    return Response.json({ ...parsed, fromCache: false, model: result.model });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
