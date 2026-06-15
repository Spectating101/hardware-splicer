import { callJarvis } from "@/lib/jarvis/client";
import {
  buildLlmPlannerPrompt,
  expandAndDetectTools,
  mergeToolPlans,
  parseLlmToolPlan,
} from "@/lib/jarvis/build-tool-planner";
import type { BuildIntentContext } from "@/lib/jarvis/build-agent";

export const runtime = "nodejs";

interface PlanRequest {
  text: string;
  context?: BuildIntentContext;
}

export async function POST(req: Request) {
  let body: PlanRequest;
  try {
    body = await req.json() as PlanRequest;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const text = (body.text ?? "").trim();
  if (!text) {
    return Response.json({ error: "text required" }, { status: 400 });
  }

  const ctx = body.context ?? {};
  const regexPlan = expandAndDetectTools(text, ctx);

  try {
    const prompt = buildLlmPlannerPrompt(text, ctx);
    const result = await callJarvis({
      flow: "chat",
      messages: [{ role: "user", content: prompt }],
      maxTokens: 400,
    });
    const llmPlan = parseLlmToolPlan(result.text);
    const invocations = mergeToolPlans(llmPlan, regexPlan);
    return Response.json({
      invocations,
      source: llmPlan.length > 0 ? "llm+regex" : "regex",
      model: result.model,
    });
  } catch {
    return Response.json({
      invocations: regexPlan,
      source: "regex",
      model: "offline",
    });
  }
}
