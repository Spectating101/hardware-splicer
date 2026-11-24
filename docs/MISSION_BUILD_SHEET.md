# Mission engineering review sheet (read-only)

A fabrication mission can hold a proposal, software evaluations, retained output and unresolved
physical facts, each with different authority. The review sheet at
`/engineering/missions?project=<id>&mission=<id>` shows them side by side without giving an agent
or the page any build authority. The page only reads.

## What it shows

- Open **Engineering review sheet** on an accepted mission with at least one candidate. When there
  are several, a READY verdict applies only to the candidate it names.
- Inventory is the user's list, not a verified bill of materials. Agent-cited source IDs, named
  donors and unrecognized spec fields are shown as unverified, never as implemented design.
- Physical correctness, firmware and power-on authorization, open needs, safety concerns and each
  candidate's check results are shown in the backend's own terms.
- **Copy review sheet** copies a text summary headed "NOT BUILD INSTRUCTIONS" with the mission event
  sequence, caveats, software result hashes and any retained output. It is not a wiring plan.

## Non-generating inspection

The frontend route `/api/proxy/engineering/projects/{projectId}/missions/{missionId}/delivery`
forwards GET only to `GET /v1/projects/{projectId}/missions/{missionId}/delivery`. That backend
route reads existing evaluation artifacts and retained package manifests, checks their binding to the
mission, marks superseded or unavailable files, and exposes hashes. It never runs a check, builds a
package, approves a review or touches hardware. It reports `not_generated`, `blocked` and `available`
for the prototype review package separately, and says that file presence does not show which agent made
the file.

The proxy (`missions/forward.ts`) forwards no operator token, so it cannot act as a person, and the
route set contains no POST.

## Not in this tree

The mission start, accept, answer, hand-off and staging screens, the POST proxy routes and the
browser suite that drove them live in other open branches. This slice ships no Playwright spec.
Its checks are the backend tests (`tests/test_mission_delivery_inspection.py`,
`tests/test_mission_case_regressions.py`) and the TypeScript typecheck. The page was also exercised
once in headless Chromium against a real backend: an accepted mission with an omitted required donor,
an unrecognized spec field and a recorded `BLOCKED_UNSAFE` concern showed REVIEW ONLY, the donor gap,
the unchecked field, the unverified safety concern and `Prototype review package: blocked`, the copied
text began "NOT BUILD INSTRUCTIONS", and the page made no non-GET request.
