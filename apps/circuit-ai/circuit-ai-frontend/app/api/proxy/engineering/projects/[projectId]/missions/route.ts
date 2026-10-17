import { forwardMission, missionTarget } from "./forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  return forwardMission(request, missionTarget(projectId), "GET");
}
