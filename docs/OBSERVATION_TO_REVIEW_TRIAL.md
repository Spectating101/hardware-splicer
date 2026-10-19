# End-to-end mouse observation, comparison, proposal revision, human checkpoint

## Outcome: canonical API trial with synthetic data only

This trial executes through the actual Hardware Splicer product API in
an isolated temporary ProjectStore. It does not inspect or power hardware.
The input trace is fully visible in the generated folder under
docs/status/generated/gpt6-observation-mission-20261019.
The SHA-256 of those raw bytes appears in SYNTHETIC_MISSION_RECEIPT.json
along with the real software evaluations and final blocked terminal state.

The trial creates a test-only human-role operator token, accepts the test
mission, and never treats that synthetic identity as consent to read a user
device or approve a real build. No live operating-system input is captured.

## What happens (real HS APIs, simulated observation)

1. Register synthetic normalized event bytes as a source with
   authority ceiling declared, not a measured or inspected specimen.
2. Open and accept a mission through the real Mission API using a test token,
   explicitly labeling its USB donor unverified.
3. The software comparison examines a first agent-proposed interface
   (wrong_mouse): 0 symbolic activations versus the test expectation of 1.
   The trace SHA and source classification are preserved.
4. Register that assessment as another declared source and propose the
   initial candidate. HS's own intact_reuse test passes the internal
   adapter replay. This illustrates why passing self-generated examples
   cannot validate the proposed host alias.
5. Submit a second candidate, adapting only the software alias to the
   normalized trace's declared donor_mouse alias. The comparison emits one
   symbolic activation and HS's canonical intact_reuse executor runs
   again and produces a second hash-bound software-review bundle.
   This is software adaptation, not physical donor identity evidence.
6. Record an explicit BLOCKED_NEEDS_PHYSICAL_MEASUREMENT need referencing
   the source trace hash. End the mission with that blocked terminal state
   citing the need, rather than READY.
7. Inspect retained outputs using the canonical read-only GET /delivery.
   Both software bundles exist, and the prototype package is blocked.
   Attempts to generate a READY package or stage a build review are
   refused. Physical correctness stays UNPROVEN; power/firmware authority
   remain false.

All intermediate mission/project writes happen in the isolated test store
and are deleted at completion. Only the reproducible source fixture and
the explicitly synthetic receipt remain in this branch. Re-running
produces new random mission and source IDs.

## Reproduction

    PYTHONPATH=src python -m scripts.run_mouse_observation_mission_trial
    PYTHONPATH=src python -m pytest -q tests/test_mouse_observation_assessment.py

Compare an existing normalized JSONL trace:

    PYTHONPATH=src python -m hardware_splicer.mouse_observation_assessment \
      --trace docs/status/generated/gpt6-observation-mission-20261019/synthetic-mouse-events.jsonl \
      --origin synthetic_fixture \
      --device-alias donor_mouse --expected-actions 1 \
      --project-id demo --mission-id example --candidate-id revised

An operator-supplied trace from the read-only observer can later be
compared separately with origin operator_supplied_unverified_host_capture.
That origin remains unverified and never promotes USB identity,
calibration, force/travel measurement, readiness or safety authority.

## Actual physical checkpoint

For the next real observation, an operator must identify a specific
nonhazardous mouse, choose the exact event node, and explicitly consent
to a bounded read-only capture. Independently assessed device identity,
host mapping, physical mechanism geometry, force/travel, return, stops,
strain relief and other safety facts still require real evidence.
No live capture was attempted here. No physical promotion is automatic.

The result is a tested software integration of observe, compare, revise,
verify, and defer to human review; it is not a claim that an agent built
a working foot pedal.
