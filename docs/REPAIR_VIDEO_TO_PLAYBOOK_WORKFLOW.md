# Repair Video To Playbook Workflow

Circuit-AI can use repair, cleaning, and restoration videos as reference material, then turn the repair intent into an independent, safety-first playbook.

The goal is not to clone a creator's video. The goal is to help a user reproduce the repair process on their own device with:
- scan evidence
- symptoms
- safety gates
- tools and parts
- diagnostic measurements
- stop conditions
- before/after validation

## Source Patterns

The current implementation supports four repair-video patterns:

1. Console/handheld cleaning and restoration
   - Typical sources: retro console restoration, dirty controller cleaning, corroded battery terminal repair.
   - Useful for: handheld consoles, controllers, toys, small gadgets.

2. Board-level electronic fault finding
   - Typical sources: PCB short finding, console board repair, MOSFET/regulator fault isolation.
   - Useful for: small powered electronics, control boards, actuator modules.

3. Bulk broken-device triage
   - Typical sources: "I bought broken electronics" repair/resale videos.
   - Useful for: salvage businesses, e-commerce arbitrage, repairability scoring.

4. Mechanical cleaning and cosmetic restoration
   - Typical sources: shell cleaning, contact cleaning, rust/corrosion cleanup, retrobright-style plastic restoration.
   - Useful for: cosmetic recovery with electronics protection.

## Inputs

Minimum:
- video title or URL
- device hint
- observed actions or symptoms

Better:
- Circuit-AI analysis JSON from a board/device photo
- closeups of PCB, labels, connectors, corrosion, burns, and broken parts
- measurements: input voltage, rail-to-ground resistance, startup current

Best:
- top and bottom board photos
- before/after cleaning photos
- model number and board revision
- symptom history
- known-good reference photo or board

## Output Artifacts

The workflow produces:
- video pattern classification
- watch map for what the operator should capture while watching
- Circuit-AI inputs required to reproduce the repair
- independent recreation flow
- repair encyclopedia guide
- quality gates
- operator capture checklist
- difficulty and can-follow score

Example output:
- `eval/rerun_full_product/image_demo_pcb/video_repair_playbook.json`
- `eval/rerun_full_product/image_demo_pcb/video_repair_playbook.md`

## CLI

```bash
python3 scripts/generate_video_repair_playbook.py \
  --title "Fixing a broken USB desk fan that will not spin" \
  --channel "Repair video reference" \
  --url "https://www.youtube.com/results?search_query=usb+desk+fan+repair+not+spinning" \
  --observed-action "inspect PCB and motor driver" \
  --observed-action "test power input and motor load" \
  --observed-action "repair connector or driver stage" \
  --analysis eval/rerun_full_product/image_demo_pcb/analysis.json \
  --symptom "fan will not spin" \
  --symptom "driver board gets hot" \
  --symptom "works if the connector is wiggled" \
  --device-hint "USB desk fan / small motorized gadget" \
  --output eval/rerun_full_product/image_demo_pcb/video_repair_playbook.json \
  --markdown-output eval/rerun_full_product/image_demo_pcb/video_repair_playbook.md
```

## Why This Is Better Than Just Watching A Video

Repair videos often show the sequence visually, but they may omit:
- exact voltage/current measurements
- failure branches
- safety setup
- part rating checks
- reassembly validation
- failed attempts or uncertainty

Circuit-AI fills that gap by forcing the repair into a repeatable structure:
- what evidence to capture
- what subsystem is suspected
- what test confirms or rejects the fault
- what repair is allowed only after confirmation
- what proves the fix worked

## Boundary

Do not copy the creator's narration, transcript, or exact edit. Treat the video as a reference and produce an independent guide from observable repair intent plus your own device evidence.

High-voltage, lithium battery, microwave, CRT, EV, and mains appliance repairs need stricter workflows than this small-gadget lane.
