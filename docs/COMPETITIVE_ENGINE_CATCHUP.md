# Competitive Engine Catch-Up Plan

Goal: competitive_unknown_electronics_intake_engine

Start from an unknown item or listing, then route into repair, salvage, build, source/sell, safety review, or evidence collection.

## Immediate Actions

### fine_tune_component_detector
- Lane: component_detection
- Why: local YOLO datasets exist; smoke-ranked checkpoints can be replaced by measured mAP validation
- Command: `python3 scripts/train_pcb_detector.py --data-yaml datasets/electrocom61/data.yaml --base-model models/pcb/pcb_components_yolo11n_thawed.pt --epochs 50 --imgsz 640 --output-dir pcb_runs/competitive_component_v1`

### expand_golden_defect_eval
- Lane: defect_detection
- Why: DeepPCB subset is available; expand sample count and track localization metrics
- Command: `python3 scripts/fetch_deeppcb_subset.py --split test --limit 250 --output-dir datasets/deeppcb_subset && python3 scripts/evaluate_deeppcb_golden.py --manifest datasets/deeppcb_subset/manifest.json --output eval/deeppcb_golden_metrics.json`

### capture_protocol
- Lane: production_aoi_readiness
- Why: competitors win with controlled capture; random photos need quality gates and guided retake prompts
- Command: `document and enforce lighting/focus/angle retake gates in intake and scan flows`

### repair_packs
- Lane: repair_coverage
- Why: iFixit-style breadth must be verticalized; strong lanes need model-specific packs first
- Command: `build packs for USB gadgets, retro handhelds/controllers, sensor/display modules`

## Source Readiness

### ElectroCom61 local YOLO corpus
- Task: component_detection
- Readiness: ready
- URL: datasets/electrocom61/data.yaml
- Gap closed: improves component localization and class diversity beyond smoke checkpoints
- License note: local prepared dataset; verify upstream license before redistribution

### DeepPCB
- Task: golden_defect_detection
- Readiness: ready
- URL: https://github.com/tangsanli5201/DeepPCB
- Gap closed: adds golden-reference defect localization and AOI-style evaluation
- License note: research dataset; confirm downstream redistribution terms

### FICS PCB Image Collection / FPIC
- Task: component_detection
- Readiness: partial
- URL: https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/
- Gap closed: improves generalization from synthetic/curated parts to real board photos
- License note: academic dataset; follow site terms and attribution requirements

### HRIPCB-style high-resolution PCB defect corpora
- Task: defect_detection
- Readiness: needs_fetch
- URL: https://github.com/Charmve/Surface-Defect-Detection/tree/master/DeepPCB
- Gap closed: broadens defect samples beyond a small DeepPCB subset
- License note: mirror availability varies; verify original dataset terms

### iFixit
- Task: known_model_repair_guides
- Readiness: reference_only
- URL: https://www.ifixit.com/
- Gap closed: sets the bar for model-specific repair breadth
- License note: do not copy guides; use as market/coverage reference and link-out inspiration only

### DaoAI AOI
- Task: production_aoi
- Readiness: reference_only
- URL: https://www.daoai.com/aoi
- Gap closed: defines production AOI expectations for setup, defect classes, and false calls
- License note: competitor reference only

### Delvitech Horus
- Task: production_aoi
- Readiness: reference_only
- URL: https://delvi.tech/technology/horus/
- Gap closed: defines the calibrated-inspection ceiling we should not overclaim against
- License note: competitor reference only

### Flux
- Task: ai_pcb_design
- Readiness: reference_only
- URL: https://www.flux.ai/
- Gap closed: defines expectations for build/design UX after salvage modules are chosen
- License note: competitor reference only

### Circuit Mind
- Task: ai_electronics_design
- Readiness: reference_only
- URL: https://www.circuitmind.io/
- Gap closed: sets expectations for requirements-to-schematic automation
- License note: competitor reference only

## Production Gates

- component_detection: minimum_map50: 0.65, target_map50: 0.8
- defect_detection: minimum_iou50_recall: 0.7, target_iou50_recall: 0.9
- case_routing: minimum_human_acceptance: 0.8, target_human_acceptance: 0.92
- safety: minimum_hazard_recall: 0.98, target_hazard_recall: 0.995
