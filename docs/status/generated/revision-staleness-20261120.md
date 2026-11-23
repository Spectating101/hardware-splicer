# Revision staleness on a saved digital study (2026-11-20)

## Links that already existed

- Each digital study revision owns one sealed run (`sealed-run.json`): `parent_revision`, requirements, source hashes, checks (`summary.constraints`) and a SHA256 per artifact, including `STUDY.zip`. `validated_run` rechecks those hashes before any claim is used.
- `GET .../digital/compare` reported requirement changes and per-check transitions between two revisions.
- The assurance graph (`engineering_assurance.py`) and `POST .../assurance/evidence-delta` judge staleness from the source/claim graph. Their outputs come only from `preFabricationPlan`/`engineeringPlan` and `engineeringBlockers`.

## What was missing

Digital snapshots carry `digitalStudy` and none of those surfaces, so their assurance graph had zero outputs and the bench showed "Evidence-to-revision link · not linked". Nothing tied a check to the requirements it reads.

## What changed

- `digital_cases.CHECK_REQUIREMENTS` records which requirements each Fielddeck 5 check reads. A declaration applies only to a run whose evaluator files have the declared SHA256 values. Every other run, and any check not listed, depends on every requirement.
- `study_evidence.py` loads a revision's sealed checks and adds them to the assurance graph as `check` outputs. Each output is bound to its revision, run, seal, snapshot and package hashes. A failed check sets the graph status to `blocked`.
- The evidence delta now compares the base and candidate revisions' study inputs. A base check is `stale` (keeping its revision and run ID, never counted for the candidate) when an input it reads changed, the check is absent from the rerun, or its rerun result differs. Otherwise it is `retained`. The response lists rerun results, failing checks, and the before/after `STUDY.zip` with hashes.
- The bench renders these rows as returned.

## Chain run (`revision-staleness-20261120.log` / `.json`)

On Fielddeck 5, the work-runtime target changed from 2.5 h to 3.5 h. Revision 1 was left unchanged and revision 2 was created by a native rerun of the study. `work_runtime` from revision 1 is stale. In revision 2 it fails, at 3.166 h against a 3.5 h limit, and that failure is kept. The two supply checks are retained, and their reruns match. Nothing is marked ready or authorised.

## Still not linked

- The rerun covers the whole study, not individual checks.
- Non-digital projects still show staleness only after source or claim edits.
- Only Fielddeck 5 declares which requirements each check reads.
- No Policy Lab or Cite adapter exists.
