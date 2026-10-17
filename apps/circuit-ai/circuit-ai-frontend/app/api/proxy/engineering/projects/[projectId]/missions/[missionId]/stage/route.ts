import { forwardMission, missionTarget } from "../../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string }> };

/** Opens a project review of the READY design. It promotes nothing; a person decides that review elsewhere. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, missionId } = await context.params;
  return forwardMission(
    request,
    missionTarget(projectId, `/${encodeURIComponent(missionId)}/stage`),
    "POST",
    (await request.text()) || "{}",
  );
}
