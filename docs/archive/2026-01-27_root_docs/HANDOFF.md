# Circuit-AI Handoff & Quick Ops

This is a concise guide to pick up the project and reproduce the key outputs.

## Prereqs
- Python env with project deps installed (`pip install .`).
- Set your LLM key in `.env.local` (already used in recent runs).
- NGSpice optional; if present, design assistant auto-runs it.

## Fast Demos
- Vision + checklist: `circuit-ai-cli -i <board.jpg> "Summarize this board"`  
  Outputs console report with inspection checklist + `analyzed_pcb.png`.
- Design + netlist/Spice:  
  `python scripts/design_assistant.py --use-case "USB-C PD trigger delivering 12V/3A" --constraints "3A continuous, safe" --out-prefix out/design/usb_pd`  
  Saves `.netlist.json`, `.spice.cir`, `.txt`, and runs NGSpice if available.
- Demo pack (ready-made sample): `python scripts/demo_bundle.py --out demo_output`

## Evaluation
- Current artifacts: `eval_results.csv`, `eval_summary.json` (6-image subset from `datasets/gemini_eval/images/`; labels in `datasets/gemini_eval/labels.csv`).
- Run eval on a labeled set:  
  ```
  set -a; source .env.local
  python scripts/eval_labeled.py \
    --images <folder> \
    --labels <labels.csv> \
    --mode standard \
    --output eval_results.csv \
    --summary-out eval_summary.json \
    --max-size 1200
  ```
- Labels CSV format: `filename,label`
- If you add new images, place them under `datasets/gemini_eval/images/` (or another folder) and update the labels CSV accordingly.

## Robot/Bench Readiness
- ArUco locator: `python scripts/aruco_scan.py --image <photo_with_markers> --output aruco_markers.json`
- Task plan JSON (inspection steps + detection summary):  
  `python scripts/task_planner.py --image <board.jpg> --out task_plan.json`

## EDA Handoff
- Convert design netlist JSON to KiCad netlist XML:  
  `python scripts/netlist_to_kicad.py --input out/design/usb_pd.netlist.json --output usb_pd.kicad_netlist.xml`

## Optional Enclosures
- Splicer bridge (if adjacent `3d-splicer` repo + service):  
  `python scripts/splicer_bridge.py --board-spec <board.json> --splicer-url http://localhost:8000 --out splicer_artifacts`

## Notes
- Inspection checklist is embedded in every vision report and also returned as structured data (`inspection_checklist`).
- Detection summary now includes per-class counts to support downstream planning.
- If evals time out on very large images, use `--max-size` to downscale (default 2000; 1200 used in last run).
