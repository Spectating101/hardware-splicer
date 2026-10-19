import { forwardMission, missionTarget } from "../../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string }> };

/** Read-only inspection: never run checks, generate a ZIP, or grant build authority. */
export async function GET(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(request, missionTarget(projectId, "/" + encodeURIComponent(missionId) + "/delivery"), "GET");
}
