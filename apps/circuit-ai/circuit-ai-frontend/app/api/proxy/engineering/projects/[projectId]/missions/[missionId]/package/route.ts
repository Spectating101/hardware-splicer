import { forwardMission, missionTarget } from "../../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string }> };

/** POST builds the package and returns its manifest; GET downloads the ZIP. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(request, missionTarget(projectId, `/${encodeURIComponent(missionId)}/package`), "POST", "{}");
}

export async function GET(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(request, missionTarget(projectId, `/${encodeURIComponent(missionId)}/package`), "GET");
}
