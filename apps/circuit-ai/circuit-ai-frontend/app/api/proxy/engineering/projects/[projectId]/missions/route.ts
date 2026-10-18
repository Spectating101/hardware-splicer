import { forwardMission, missionTarget } from "./forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  return forwardMission(request, missionTarget(projectId), "GET");
}

/** Opens a mission. With a person's operator token the backend names them as the opener; without one the body's author is used. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId } = await context.params;
  return forwardMission(request, missionTarget(projectId), "POST", (await request.text()) || "{}");
}
