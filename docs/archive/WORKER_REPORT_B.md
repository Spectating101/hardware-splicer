# Task B: reclaimed parts in the device planner

Implemented the smallest advisory handoff. No device-library entries, wiring rules, device specs or authority states are changed. Nothing identifies a reclaimed chip, establishes compatibility, treats a recorded reading as a pass, or approves building, powering or release.

## Changes and files

- `src/hardware_splicer/device_reclaim.py`: `match_reclaimed_parts` validates a reclaim list (at most 300 rows; bounded printable text), preserves reported markings/kinds, and compares only whole library `name` or explicit `mpn` fields. Returns each row's matches, their exact/variant tiers, library source and explicit advisory limits. Numeric markings, including NaN, infinity, huge integers and booleans, are refused as non-text; no numeric dimensions or readings are consumed, so no new numeric coercion needs `finite_number`.
- `src/hardware_splicer/part_lookup.py`: extracted the existing exact/variant name rules into `name_match_tier`, including package/grade suffixes and trailing KiCad `x` placeholders. Family suggestions remain in part lookup and are excluded from this handoff.
- `src/hardware_splicer/device_api.py`: added stateless `POST /v1/devices/reclaim-matches`, with 422 validation errors and a streamed 64 KB body limit. Shared the existing device-plan JSON reader without changing its error contract.
- `apps/circuit-ai/circuit-ai-frontend/app/api/proxy/engineering/devices/reclaim-matches/route.ts`: matching proxy with the same streamed limit and existing authentication/error forwarding conventions.
- `apps/circuit-ai/circuit-ai-frontend/components/engineering/assembly-viewer.tsx`: added the optional capture-plan `component` field to its part type.
- `apps/circuit-ai/circuit-ai-frontend/lib/reclaim.ts`: reclaim rows now also carry the typed marking and reported component kind. Lookup MPNs never substitute for typed markings in the handoff; CSV output stays the same.
- `apps/circuit-ai/circuit-ai-frontend/lib/device-reclaim.ts`: shared request/types and session-storage key.
- `apps/circuit-ai/circuit-ai-frontend/app/engineering/donor/page.tsx`: per-matching-row `reclaim-device-match` links and advisory text. Stale plans hide links; obsolete requests are aborted. Clicking passes only input fields through session storage; blocked storage is reported.
- `apps/circuit-ai/circuit-ai-frontend/app/engineering/device/page.tsx`: when opened with `from=donor`, checks the stored input through the backend again and shows a separate advisory `device-on-hand` list. The example/spec/shopping list and wiring remain untouched.
- `scripts/mock_canonical_project_studio_backend.py`: added a handler that reuses the real matcher and bounded JSON reader.
- `docs/DEVICE_PLAN.md`, `docs/DONOR_CAPTURE.md`: documented endpoint, handoff and limits.
- `tests/test_device_reclaim.py`: added matcher and endpoint regression tests.

## Verification

The new test file failed against the original tree because the matcher did not exist. An additional check loaded the original `device_api.py` from HEAD and confirmed the new route returned 404, so its endpoint assertions fail on the old behavior.

Focused tests cover real-library matches and exclusions, both suffix directions, trailing `x`, family/different-digit exclusions, explicit MPNs using synthetic test-only entries, preservation of reported kinds, hidden/control text, invalid shapes, row limits, numeric/non-text inputs, malformed/deep JSON, declared and streamed body limits, stopping the stream immediately, integration from a real capture plan through the product API, and no project/library/plan mutation.

Initial requested command:

```sh
PYTHONPATH=src /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/.venv/bin/python -m pytest -q tests/test_device_reclaim.py tests/test_device_plan.py tests/test_donor_capture.py tests/test_part_lookup.py
```

This sandbox denies socket-pair sends (`PermissionError: [Errno 1] Operation not permitted`), stalling asyncio wakeups in Starlette TestClient. The unchanged existing device-library endpoint test stalled identically. The stalled runs were interrupted.

Retried with a temporary test-only pytest plugin that schedules a 10 ms recurring timer on each asyncio loop, allowing pending thread callbacks to run without socket sends. No application or test assertions were modified. The helper was under this worktree's ignored `.cache/pytest-sandbox`, and was removed afterward.

```sh
PYTHONPATH=src:.cache/pytest-sandbox /home/phyrexian/Downloads/llm_automation/project_portfolio/Hardware-Splicer/.venv/bin/python -m pytest -q -p hs_sandbox_poll tests/test_device_reclaim.py tests/test_device_plan.py tests/test_donor_capture.py tests/test_part_lookup.py
```

Result: **195 passed**, 14 existing dependency/status-constant deprecation warnings, 13.52 seconds. Both requested existing regression files are green with that environment workaround.

- `npx tsc --noEmit -p .` inside the frontend: passed.
- Mock-handler smoke check: 200 response equals the real matcher; invalid input returns 422; oversized input returns 413.
- React review: stable memoized reclaim input, aborted obsolete fetches, browser storage only after mount, text rendered through React, existing styles and test-id conventions.
- `git diff --check`: passed.

No Next build, Playwright, full Python suite or commits were run.

## Limits / anything unsure

The existing device library contains two complete modules with descriptive names and no explicit MPN fields. Only a whole-name match or an allowed suffix variant is offered; `SSD1306` and `ESP32-WROOM-32E` do not become matches for the complete modules. This deliberately means few ordinary chip markings will match today. No aliases or library data were invented.

The frontend handoff was typechecked and reviewed, but not exercised in a browser under the requested limits. Session storage must be available for a link click to transfer the reclaim list. The normal TestClient command remains constrained by this execution sandbox's asyncio socket-send restriction.

All changes are uncommitted in this worktree.
