import { forwardMission, missionTarget } from "../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(request, missionTarget(projectId, `/${encodeURIComponent(missionId)}`), "GET");
}
