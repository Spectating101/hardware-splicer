import { forwardMission, missionTarget } from "../../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string }> };

/** A person accepts a mission once. The operator token travels in its own header; the backend decides who it is. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(request, missionTarget(projectId, `/${encodeURIComponent(missionId)}/accept`), "POST", "{}");
}
