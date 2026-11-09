# Physical action gate: genuine schematic reference vs verified target board

In the real-source pilot PR #327, Gekkio's DMG-CPU-06 KiCad netlist
correctly identifies reference connections such as DC1 pin 4 on
/Power/BT+. Gemini used those connections in its differential.

**Failure discovered:** even though the repair publisher's mainboard
revision was only reported, not verified by photo or physical examination,
the model proposed a test directly between internal DC1 pins 3 and 4.
This could be a legitimate *reference design* concept, but **cannot be
authorized as advice for the actual device** without confirming its
specific hardware revision and safe board access.

## Implemented

1. Generic physical-target pin-action guard in
   restoration_board_action_gate.py. It inspects safe-test and next-test
   prose for explicit component-pin actions, e.g. DC1 pin 4, SW1.2,
   or pin 3 of DC1. It fails closed when the source metadata marks
   the target board identity unverified.
2. The original source-extracted net reference may still be discussed
   as **circuit architecture** or a diagnostic hypothesis. The gate
   is not an excuse to pretend the target was physically measured.
3. Any corrective model turn must validate the exact original model
   receipt digest, source evidence SHA, prompt hash, same model ID,
   and original real schematic tool hash. Exactly **one** correction
   attempt is allowed and its new receipt is stored separately.
4. No new real-life observations, battery measurements, creator repair
   outcomes, board photographs, tool purchases or device changes enter
   the correction. If the model still proposes unsafe or unsupported
   test points, its output is rejected. Previous model text is not
   silently erased or rewritten.
5. No modification to the CC-BY-4.0 pinned KiCad reference or the
   original A/B model result in PR #327.

This is a deliberately narrow regex safety filter. It does NOT
guarantee that all dangerous repair proposals are detected; formal
device safety, technician verification and calibration are separate.

## Acceptance boundary

- "BT1 pin 1 connects to DC1 pin 4 on Gekkio's reference netlist" is
  an **attributed source circuit claim**.
- "Measure DC1 pin 4 on this actual device" is a **physical test
  instruction** and MUST NOT be recommended until the actual board
  revision is verified and appropriate electrical safety is established.
- External battery compartment inspection and a request to verify
  the printed PCB revision are permissible cautious first steps.
- The source graph remains DECLARED, not MEASURED/VERIFIED/AUTHORIZED.

## Reproducibility

The initial live source+model test is in
real_dmg_kicad_model_ab.json from PR #327.

A single new correction can be run with:

    PYTHONPATH=src python3 examples/restoration_video_bench/real_schematic/run_dmg_board_gate.py \
      --source-checkout /tmp/hs-source-gb-schematics \
      --out /tmp/dmg_verified_board_gate.json

The original prediction and source hashes are read-only.
