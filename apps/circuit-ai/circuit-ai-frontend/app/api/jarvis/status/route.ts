import { getJarvisProviderStatus } from "@/lib/jarvis/client";
import { getVisionBudgetSnapshotSync } from "@/lib/jarvis/vision-budget";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const jarvis = getJarvisProviderStatus("chat");
  return Response.json({
    status: "success",
    jarvis,
    metadata: {
      secrets_returned: false,
      note: "Copilot handles text and evidence-mediated image flows. Qwen can be selected for paid native image flows only when a Qwen key and explicit paid-vision budget cap are configured.",
      image_evidence_bridge: {
        backend_url: process.env.CIRCUIT_AI_VISION_URL || process.env.NEXT_PUBLIC_VISION_API_URL || "http://127.0.0.1:8000",
        analyzer_auth_configured: Boolean(process.env.CIRCUIT_AI_API_KEY),
        raw_multimodal_pixels_sent_to_copilot_cli: false,
      },
      qwen_native_vision: {
        configured: jarvis.configured.qwen,
        disabled: jarvis.qwenRouting.disabled,
        selected_when: "JARVIS_VISION_PROVIDER=qwen",
        selected_model: jarvis.qwenRouting.selectedVisionModel,
        model_rotation: jarvis.qwenRouting.visionRotation,
        low_quota_models: jarvis.qwenRouting.lowQuotaModels,
        raw_multimodal_pixels_sent_to_qwen: !jarvis.qwenRouting.disabled,
      },
      paid_vision_budget: getVisionBudgetSnapshotSync(),
    },
  });
}
