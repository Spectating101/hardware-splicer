import { forwardMission, missionTarget } from "../../../../forward";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ projectId: string; missionId: string; needSeq: string }> };

/** A person types a reading for a measurement request. The backend builds the evidence and takes the decider from the token. */
export async function POST(request: Request, context: RouteContext) {
  const { projectId, missionId, needSeq } = await context.params;
  return forwardMission(
    request,
    missionTarget(projectId, `/${encodeURIComponent(missionId)}/needs/${encodeURIComponent(needSeq)}/answer`),
    "POST",
    (await request.text()) || "{}",
  );
}
