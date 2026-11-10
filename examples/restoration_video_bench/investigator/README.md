# HS Repair Investigator — real C64 field pilot

Purpose: assemble previous HS restoration work into one reproducible
evidence → actual engineering reference → model diagnosis →
source-limited follow-up → offline audit → interactive report workflow.

## New device and public sources

Case: Commodore 64 ASSY 250407 with missing ICs and previous repair work,
Jan Beta, May 12 2025.

- Repair video: https://www.youtube.com/watch?v=mkGEXlQ84wk
  Auto-generated English captions SHA256:
  59f29eaf1c236b2f621facd9e810619be657cc4cde9ac3e5977e73d42cfe0dcb.
- Open KiCad reference:
  https://github.com/bwack/C64-250407-Replica-KiCad
  Upstream commit: 9bf17bb868248b12fb12210d66be3a37ec4ab832.
  Licence: CERN Open Hardware Licence v1.2.
  Attribution: bwack and original PCB reverse engineering by Michael K.
  (Der Alte Bastler). This replica may differ from historic 250407
  Rev A/B and KU boards; it is not a verified target boardview.
- KiCad 9.0.2 exported 230 components, 250 nets. The source snapshot
  retains 17 selected supply, reset, clock, bus and DRAM nets (199
  connected pin records). U7 pin 6 appears on +5V; U7 pin 40 on RESET,
  and U7 pin 1 on PHI0. All are reference pin claims, not measurements.
- KiCad issued schematic annotation warnings. They remain disclosed.

The creator video description contains later repair chapter names, but
the model input is restricted to 0–120 seconds of opening speech and
120–210 seconds of pre-repair visual-inspection narration. No later
repairs, creator outcomes, voltage measurements or images are fed to
the model. The experimenter could see video descriptions while finding
the source; this is NOT an independent blinded benchmark.

## Run the actual workflow

Uses the existing Antigravity Gemini CLI subscription; no API key or
silent paid fallback. The upstream source checkout and full YouTube
WebVTT are deliberately not committed to this repository.

First verify the actual original KiCad source, revision and source nets:

    PYTHONPATH=src python3 examples/restoration_video_bench/investigator/verify_kicad_reference.py \
      --captions-vtt /tmp/hs-c64-video-unseen-20261110/mkGEXlQ84wk.en-orig.vtt \
      --schematic-checkout /tmp/hs-source-c64-250407

Then run four precommitted model calls in alternating arm order:

    PYTHONPATH=src python3 examples/restoration_video_bench/investigator/run_investigator.py \
      --captions-vtt /tmp/hs-c64-video-unseen-20261110/mkGEXlQ84wk.en-orig.vtt \
      --schematic-checkout /tmp/hs-source-c64-250407 \
      --out /tmp/hs_c64_investigator_live.json

The opening stage runs plain Gemini and then HS+KiCad Gemini, once
each. The inspection stage runs HS+KiCad and then plain Gemini, once
each. Later observations are chained to the model receipts from the
opening stage, with unchanged first-stage evidence. Invalid replies
are preserved and block follow-up rather than being rerolled.

After inference is frozen, generate the offline forensic report:

    PYTHONPATH=src python3 examples/restoration_video_bench/investigator/render_investigator.py \
      --record /tmp/hs_c64_investigator_live.json \
      --html /tmp/hs_c64_investigator.html \
      --audit /tmp/hs_c64_audit.json \
      --public-record /tmp/hs_c64_investigator_public.json

The exact, potentially copyrighted model-input caption excerpts remain in
the original private local inference file and are not redistributed.
The public standalone HTML and machine JSON replace those excerpts
with brief human-authored paraphrases, preserving each original evidence
text hash, timestamp and frozen model-receipt digest. Independent replay
requires obtaining the actual public VTT again; a redacted copy alone
cannot fully reconstruct the original model prompt.

Open the single HTML file in a browser. It includes working phase and
model toggles, original E-coded source observations, real KiCad net/pin
data, integrity ledger, and a local JSON export. No CDN, API, server
or further paid inference is needed.

## Acceptance checks

1. The same native HS repair intake and exact first-stage video text
   are supplied to plain and source-assisted model arms.
2. The treatment invokes the real native engineering source graph and
   supplies actual KiCad-derived circuit connectivity, with source
   hashes, licensing and revision limitations.
3. Both arms use Gemini 3.8 Flash Low and the same diagnostic JSON
   schema, but have different system prompts and token budgets.
   Therefore the result cannot isolate the graph effect by itself.
4. Every model receipt includes original evidence SHA, prompt SHA,
   model identity, source graph SHA where applicable, and parent
   receipt SHA for follow-up. Failure is reported, not hidden.
5. No physical board revision is verified, so internal pin-specific
   test instructions remain prohibited.
6. No guessed electrical thresholds, live probing, safety bypass,
   destructive repairs or purchases are authorized.
7. Original reference files can be re-exported with KiCad and
   compared against all 17 selected net records.
8. No repair outcome is scored during inference. One case cannot
   support a broad accuracy or real-world commercial claim.

## Consolidating existing draft PRs

The main restoration stack whose code feeds this entrypoint is:

    #318 → #319 → #320 → #322 → #323 → #324 →
    #326 → #327 → #328 → #329 → #330 → THIS PR

Separate post-outcome review PRs: #321 (based on #320) and #325
(based on #324). They should remain independently reviewable, not
introduced as initial model evidence. #317 is a different ZMK
firmware workstream and remains separate.

The experiment unifies the runtime, but these drafts have NOT
all been merged into the main repository branch. Human review
and careful base retargeting remain necessary. All preceding
restoration drafts were mergeable with green checks at the
preimplementation audit.

## What this does NOT establish

No independent instrument recordings, physical board photograph
verification, direct video-frame vision, hardware actuation, real
physical repair, independently proven outcome, or statistically
demonstrated diagnosis improvement versus plain Gemini. This is
a substantial source-evidence workflow, not yet an autonomous lab.
