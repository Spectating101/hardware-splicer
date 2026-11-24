# Mission engineering review sheet — read-only handoff

A fabrication mission can have a proposal, software evaluations, retained output, and
unresolved physical facts, all with different authority. The engineering review sheet under
/engineering/missions makes those distinctions legible without giving an agent build authority.

## Surface and input

- Open **Engineering review sheet** on any accepted mission with a proposal.
- Choose one agent-proposed candidate when multiple candidates exist. A READY terminal applies
  only to its named candidate, not all the agent's proposals.
- Inventory is displayed as user-listed, not a verified bill of materials. Agent-cited source IDs,
  named donors and unrecognized spec fields are not treated as verified design implementation.
- Physical correctness, physical authorization, unresolved needs, safety concerns and candidate
  check results are displayed in their actual backend terms.
- Copy review sheet copies an inspectable text summary, including the exact mission event sequence,
  source/donor caveats, software result hashes, and any retained output returned by inspection.
  The copied text is not a wiring plan or fabrication instruction.

## Evidence and non-generating file inspection

The read-only frontend GET route at
/api/proxy/engineering/projects/{projectId}/missions/{missionId}/delivery forwards to
the canonical backend GET /v1/projects/{projectId}/missions/{missionId}/delivery.
That backend route:

- reads existing evaluation artifacts and currently retained package manifests;
- checks package/mission binding, identifies superseded or unavailable files and exposes hashes;
- never generates new output or performs software checks, fabrication, actuation or review approval;
- reports not_generated versus blocked versus available for the prototype review package;
- explicitly says file presence alone does not establish which agent created it.

The sheet only enumerates files in the chosen candidate's inspected recorded_files.
The existing separate Hand-off panel is the only UI path here that explicitly asks the
backend to generate the ready candidate's review package.

## Verification

The real missions Playwright test suite checks:

1. An unverified, donor-omitting, unrecognized-field proposal carrying BLOCKED_UNSAFE is
   review-only; no action is authorized, no file is invented, and opening/copying leaves
   the mission event sequence unchanged.
2. A READY_FOR_HUMAN_BUILD software verdict displays two retained HS check artifacts but
   says the prototype package is not generated until the person explicitly clicks the
   preexisting Hand-off generation action; refreshed inspection then reports the real
   package hash, size and unknown producer attribution.

No physical device is used or evaluated by these tests. The sheet does not constitute a
safety certification, manufacturing instruction, accessibility suitability claim or sale approval.
