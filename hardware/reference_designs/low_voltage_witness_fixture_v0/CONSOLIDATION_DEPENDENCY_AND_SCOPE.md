# Witness-board consolidation: dependency, coverage and cleanup decisions

**Review date:** 20 November 2026
**Canonical reviewed source:** HS PR #370, commit d035888fec705c44869d4d752011967654ae76d5
**Review state:** SOFTWARE INTEGRATION VERIFIED; PHYSICAL/FABRICATION HOLD.
This is a code-review handoff, not a technical production authorization.

## One canonical baseline, not six rival design releases

The canonical witness *source* PR is #370 (branch
feature/witness-consolidated-review-20261120). It was created by squashing
six previous witness branches onto the #354 feasibility foundation:

| Historical draft | Work incorporated into the consolidated source |
|---|---|
| #356 | Editable KiCad board, schematic, 10-ohm SPICE and pinned synthetic INA228 / Policy Lab replay |
| #358 | Independent power/measurement/fuse readiness audit |
| #360 | 1%/5% bias and timing discrimination under synthetic TEST_FIXTURE |
| #364 | Named 12-ohm load candidates, G1 evidence intake |
| #367 | Dual-DMM SCPI mock, protection preflight, combined G1 HOLD |
| #368 | Source-OVP comparison, current limits and laboratory-borrowing decision |

**Upstream dependencies:** #370 targets #354, which builds upon #351
and the separately reviewed integration/github-features-20261116 branch.
Neither #370 nor its upstream foundation is already integrated into
main. Do not rebase directly onto main or erase those dependencies
without a separately tested integration plan.

**Policy Lab side:** The unchanged PLRS-6 receiver used by the full
source replay is pinned to commit
9f06f669e9252d2ff105581c2aaa6750d007dcd9 (PL #180).
This is a cross-repository dependency, not a HS-owned module; keep
its original source and receipt hashes intact.

## Source scope vs independent experimental work

The **committed PR #370 at d035888** runs nine integrated software
review stages, 120 focused tests, an original 10-ohm CAD/native SPICE
replay, alternate 12-ohm modeled replay, seven adversarial capture
cases, source/protection research and G1 hold checks.

Three related *separate* draft histories are **not part of these nine
executed integration stages**:

- **#359:** alternative 13-ohm operating-envelope experiment, including
  researcher-defined reserve/current criteria. It is not an approved
  replacement for the original 10-ohm source design.
- **#365:** a raw-INA228-register coherence repair that detects a forged
  primary CSV/receipt combination. This is a material G2 integrity
  improvement that should be independently reviewed and integrated
  into the single canonical draft rather than incorrectly claiming that
  the initial d035888 stage already checks it.
- **#369:** further G0–G4 and Policy Lab source-bound validation studies
  (including financial/economic admission HOLD). Do not claim they ran
  as part of the canonical nine-stage audit before actual integration
  and rerun.

Some other agent worktrees may contain uncommitted attempts to integrate
these three drafts. **Do not discard or overwrite those worktrees.**
Review exact committed contents and test the resulting source tree
before updating coverage claims.

## Executable independent review

The main review is:

    cd hardware/reference_designs/low_voltage_witness_fixture_v0
    /usr/bin/python3 review_witness.py \
      --pl-root /path/to/pl-with-pinned-PLRS6 \
      --out /new/unique/location

Successful **software-only** result: exit code **2**,
SOFTWARE_INTEGRATION_VERIFIED_PHYSICAL_HOLD, and
physical_ready=false / fabrication_allowed=false.
Exit 1 means incomplete or failed integration and must be investigated.

This cleanup adds a *separate* post-review, fail-closed evidence-scope
checker that neither edits the frozen receiver nor retests hardware:

    /usr/bin/python3 review_scope.py \
      --review /new/unique/location/review.json \
      --out /new/unique/location/scope.json

The scope checker:
1. Rechecks the expected nine executed stage labels, order, exit codes
   and a minimum of 120 reported unit tests.
2. Rehashes eight referenced output JSON artifacts and rejects any
   unexpected path, deleted/edited file or mismatched recorded digest.
3. Requires explicitly false release flags, clean-source declarations,
   and a correctly pinned Policy Lab receiver.
4. Explicitly lists the separate #359/#365/#369 work that was NOT
   in this source revision. It never infers real calibration or
   independence from SHA-256, SCPI identity strings or test results.

Successful scope result is also **exit 2**, meaning the evidence fits
the declared software-only scope but **physical HOLD** remains. Exit 1
means the review's claimed scope/provenance is inconsistent and must
not be presented as a successful consolidated audit. Output is write
once and must stay outside the source tree.

**Clean-room independent replay, 20 November:** original #370 source
d035888 yielded 120/120 tests, 9/9 expected stages, exit 2 and a
clean checkout before/after. The separate scope audit found 0 issues,
rehashing eight outputs. This does not attest to the experimental
branches or permit physical claims.

## Proposed low-risk PR housekeeping (requires repository owner review)

- Keep **#370** as the single canonical *draft* rather than merging six
  stacked drafts independently. Link these six as historical work,
  and leave their code/history available for provenance.
- Treat **#359, #365, #369** as independent test/evidence contributions
  for later reviewed integration. In particular prioritize #365's raw
  register coherence correction before claiming reliable G2 detection.
- Do not close historical drafts as if merged, delete upstream branches,
  or rewrite pinned evidence merely to simplify the PR list. Marking
  them superseded in descriptions/comments is safer; closing can follow
  owner review after source parity is confirmed.
- Do not infer that a clean KiCad DRC makes the board physically
  manufacturable: the source, DC fuse link, 4mV reference, grounding,
  calibrated meters, external clock, mounting and operator sign-off all
  remain unqualified.
- Full eventual main integration requires a separate review of #351,
  #354 and their significant upstream branch divergence.

**Release rule:** Physical fabrication, procurement, energization,
operator experiment or token issuance are NOT authorized by this
consolidation. BUILD_HOLD.md remains the governing dossier.
