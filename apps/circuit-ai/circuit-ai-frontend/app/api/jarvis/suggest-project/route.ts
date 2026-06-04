// Project suggestion endpoint. Input: parts inventory + skill level + optional
// goals. Output: ranked project list.

import { callJarvis, extractJson, type JarvisMessage } from "@/lib/jarvis/client";
import { cacheGet, cacheSet, hashString } from "@/lib/cache/component-cache";
import type { SafetyLevel, ProjectSuggestion, InventoryPart } from "@/lib/cad-types";

export const runtime = "nodejs";
export const maxDuration = 60;

interface SuggestRequest {
  inventory: Array<Partial<InventoryPart> & { label: string }>;
  skillLevel?: "beginner" | "intermediate" | "advanced";
  goals?: string;
}

interface SuggestResult {
  safety_level: SafetyLevel;
  suggestions: ProjectSuggestion[];
  fromCache?: boolean;
  model?: string;
}

export async function POST(req: Request) {
  let body: SuggestRequest;
  try {
    body = await req.json() as SuggestRequest;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!Array.isArray(body.inventory) || body.inventory.length === 0) {
    return Response.json({ error: "inventory[] required" }, { status: 400 });
  }

  const normalized = {
    inventory: body.inventory.map((p) => ({ label: p.label, qty: p.qty ?? 1, kind: p.kind ?? "unknown" })),
    skillLevel: body.skillLevel ?? "beginner",
    goals: (body.goals ?? "").trim(),
  };

  const key = hashString(JSON.stringify(normalized));
  const cached = await cacheGet<SuggestResult>("project", key);
  if (cached) return Response.json({ ...cached.value, fromCache: true, model: cached.model });

  const messages: JarvisMessage[] = [{
    role: "user",
    content: [
      { type: "text", text: `
User inventory:
${normalized.inventory.map((p) => `- ${p.label} × ${p.qty} (${p.kind})`).join("\n")}

Skill level: ${normalized.skillLevel}
${normalized.goals ? `Goals: ${normalized.goals}` : ""}

Suggest up to 6 projects, ranked by how well the inventory fits. Output the JSON schema from the system prompt.
      `.trim() },
    ],
  }];

  try {
    const result = await callJarvis({ flow: "project", messages, maxTokens: 2500 });
    const parsed = extractJson<SuggestResult>(result.text);
    if (!parsed) {
      return Response.json({ error: "Model output was not valid JSON", raw: result.text.slice(0, 500) }, { status: 502 });
    }
    await cacheSet("project", key, parsed, result.model);
    return Response.json({ ...parsed, fromCache: false, model: result.model });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }
}
