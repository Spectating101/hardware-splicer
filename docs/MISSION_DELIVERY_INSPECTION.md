# What can I get from this mission now?

The delivery inspection reports files that already exist. It does not generate a
package, run firmware, re-run checks or change mission state. It works before a
mission is READY, including software-only reuse work that cannot claim physical
readiness.

Use it for the interface's handoff panel and for experiment observers that must
not create the deliverable they are grading. It stays in the existing FastAPI
service and mission/package store; there is no new evidence database or service.

## API

`GET /v1/projects/{project_id}/missions/{mission_id}/delivery`

The response is `{"ok": true, "delivery": {...}}`, with schema
`hardware_splicer.mission_delivery_inspection.v1`:

- `last_event_seq`: the mission view this inspection started from.
- `recorded_files`: referenced software-check JSON and intact-reuse software
  bundles. Each row gives candidate, operation, evaluation sequence, content hash,
  `current` relative to the canonical repair/evidence boundary, and a download
  path only when retained bytes can be verified. Check JSON is explicitly
  `presentation: structured_data`, not a polished customer document.
- `prototype_package.status`: `blocked` when the existing READY prerequisite
  is absent; `not_generated` when eligible but no matching ZIP is retained;
  `available` when a current package is retained; `unavailable` if bounded
  storage inspection could not complete.
- `prototype_package.retained_packages`: content hashes, sizes, scope,
  recorded deliverable labels and read-only download paths. Stored prototype
  ZIPs must match this mission, terminal candidate/spec, exact event history,
  intake and plan/review hashes. Every manifest member hash/size is checked.
  This verifies retained bytes and bindings, not engineering correctness.
- `prototype_package.scan_complete`: false means the inspection is incomplete;
  never interpret incomplete inspection as proof that nothing exists.
- `prototype_package.build_path/build_method`: an explicit POST action for an
  eligible mission. This is a place to request generation, not proof that it
  has happened or will succeed.
- `unresolved_needs` and `safety_concerns`: the existing mission projections,
  not newly inferred evidence or an automatic safety assessment.
- `inspection_generated_artifacts: false`,
  `file_presence_proves_agent_delivery: false`,
  `sale_readiness: NOT_ASSESSED`, and the existing physical-correctness label.

`GET /v1/projects/{project_id}/missions/{mission_id}/delivery/packages/{package_sha256}`
downloads an already-retained current prototype review ZIP only. It never calls
the package builder. Missing or foreign packages return 404; an uninspectable
retained store returns a conflict rather than rebuilding a substitute.

Both operations are discoverable in the compact `salvage_fabrication` manifest.
Intact-reuse software bundles continue using their existing hash-bound run bundle
download route and remain `SOFTWARE_REVIEW_ONLY`. A historical row can remain
downloadable but has `current: false`; it is not output for the revised design.

## Interface handoff

Show the inspection independently of the READY-only prototype-package controls.
Keep these distinctions visible:

1. **Available now:** display/download the retained file with its actual scope.
2. **Not generated:** offer an explicit generation action where eligible.
3. **Blocked or unavailable:** show the unmet prerequisite or storage problem;
   do not substitute a green readiness badge.
4. **Historical:** show prior output separately from output for the current spec.

Firmware/enclosure labels inside a prototype package are its recorded labels.
They do not imply firmware ran, the enclosure fits, a price is known or the
product can be sold. The inspection intentionally supplies no commercial score.
It also does not yet create readable BOMs, illustrated wiring or assembly guides.

## Experimental use

The legacy `GET .../package` calls the builder and may persist a new ZIP. It is
unchanged for compatibility and must not be used to determine what an agent had
already produced.

Freeze or fingerprint the run store after model execution. Inspect via
`GET .../delivery` and only download the returned retained-file paths. Do not
call generation/staging endpoints while scoring agent delivery. If a separate
capability experiment intentionally generates a package afterwards, do that on
a copied store and label it evaluator-generated, not agent-delivered.

Package creation actors are not recorded by the existing package store, so rows
say `producer_attribution: not_recorded`. File presence alone cannot distinguish
agent, person or evaluator generation. Attribute behavior from the actual tool
trace, and distinguish completed, interrupted and unstarted model runs.

File extension/keyword presence is not a commercial acceptance test. A numeric
cost estimate needs a real cost breakdown; the word "price" is not one. An
electrical regulator is not regulatory assessment. Firmware source presence does
not establish working customer functionality or passing host tests.

## Verification

`tests/test_mission_delivery_inspection.py` checks filesystem bytes and mtimes
before/after inspection and downloads. Controls cover missing output, retained
output, cross-mission packages, mismatched specs, corrupted storage, software
output before READY, orphan ZIPs and historical output after repair. Generators
and storage writes are patched to fail in read-only controls.

These are software controls, not additional live-agent or physical experiments.

The first pre-implementation run was **7 failed, 1 passed** (the passing
missing-route 404 was not evidence that inspection existed). After implementation,
the initial focused set passed **60 tests**; the expanded focused set passed
**65 tests**, including the new corruption/orphan/history controls. These runs
overlap and must not be added together.

The final targeted run passed **350 tests, 35 warnings in 84.32s** across delivery
inspection, mission case regressions/onboarding/storage/donors/feedback/executor/
gates/delivery/concurrency/API/answers/physical-log, salvage context, intact reuse
and the mouse demo. This is not a full-repository or browser run. Warnings are
the existing duplicate OpenAPI operation-ID and deprecated HTTP-constant notices.

A read-only check against Claude's six completed Round-3 greenhouse stores found
two available check-result files in each, five prototype-package statuses
`blocked`, and one `not_generated`. No prototype package was present. Every
store's file hashes and mtimes were unchanged by inspection. This is observation
of existing runs, not six new agent runs or independent commercial validation.
