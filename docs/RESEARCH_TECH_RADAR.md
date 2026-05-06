# Research Tech Radar

Goal: research_backed_foundation_assist_for_aoi_repair_salvage

Use foundation models to propose regions, labels, masks, text, and training data; use measured detectors, golden references, and human review for production truth.

## Default Pipeline

polish_image -> YOLO/classical detections -> OCR -> foundation proposals if available -> mask/caption/marking evidence -> human review/autolabel queue -> measured retraining

## Integration Lanes

### Production component detector
- Lane: production_component_detection
- Goal: make YOLO checkpoints measurably better on PCB/component datasets
- Sources: yolo11, dinov2_clip
- Entrypoints: src/vision/detector.py, scripts/train_pcb_detector.py
- Gate: mAP50 >= 0.65 before beta, mAP50 >= 0.80 before AOI claims
- Next steps:
  - train 50+ epoch GPU runs on ElectroCom61 plus reviewed auto-labels
  - promote best.pt only after validation mAP, confusion, and sample cards pass
  - keep classical CV fallback for low-confidence scans

### Open-vocabulary discovery
- Lane: open_vocab_discovery
- Goal: notice useful unlabeled parts on random electronics and e-commerce listings
- Sources: grounding_dino, florence2, sam2
- Entrypoints: src/vision/foundation_adapters.py, src/intelligence/salvage_pipeline.py
- Gate: human label acceptance >= 70% for auto-label candidates before retraining
- Next steps:
  - generate prompt banks from device hints, symptoms, and salvage goals
  - write candidate boxes/masks into evidence metadata with source attribution
  - route unknown useful parts into teach-component and annotation-review flows

### Mask and repair-video tracking
- Lane: mask_and_video_tracking
- Goal: attach repair steps and defects to exact regions instead of loose boxes
- Sources: sam2
- Entrypoints: src/vision/golden_reference.py, src/intelligence/repair_video_playbook.py
- Gate: mask IoU >= 0.70 on reviewed defect/component masks
- Next steps:
  - use detector/open-vocab boxes as mask prompts
  - persist masks for defects, connectors, corrosion, and board outline
  - track repeated part instances across video frames for playbook generation

### Marking and label OCR
- Lane: marking_ocr
- Goal: turn tiny markings into datasheet, safety, and repair evidence
- Sources: paddleocr, florence2
- Entrypoints: src/vision/ocr_engine.py, src/vision/detector.py
- Gate: top marking string exact/normalized match >= 75% on reviewed crop set
- Next steps:
  - add optional PaddleOCR backend behind existing OCR interface
  - score text by crop quality and datasheet search consistency
  - surface uncertain markings as review tasks instead of definitive IDs

### Human-in-loop dataset growth
- Lane: human_in_loop_dataset_growth
- Goal: convert every good scan, repair case, and listing into training/eval assets
- Sources: x_anylabeling, supervision, grounding_dino, sam2
- Entrypoints: eval/competitive_engine/, datasets/, scripts/benchmark_pcb_models.py
- Gate: new labels improve validation mAP/recall without increasing false positives
- Next steps:
  - emit review bundles from foundation proposals
  - track acceptance rate, rejected labels, and retraining impact
  - separate production labels from exploratory suggestions

## Source Radar

### Ultralytics YOLO11
- Category: production_detector
- Lane: production_component_detection
- URL: https://docs.ultralytics.com/models/yolo11/
- Benefit: keeps the narrow PCB/component detector fast enough for AOI-style batch scoring and deployable edge inference
- Implementation:
  - continue using scripts/train_pcb_detector.py for measured fine-tunes
  - promote only checkpoints with validation mAP and sample-level error cards
  - use foundation proposals as auto-label candidates, not as production truth
- Risks:
  - generic COCO checkpoints are not PCB detectors
  - CPU training smoke tests prove the path, not production quality

### Meta Segment Anything Model 2
- Category: segmentation_foundation_model
- Lane: component_masks_and_video_tracking
- URL: https://github.com/facebookresearch/sam2
- Paper: https://arxiv.org/abs/2408.00714
- Benefit: turns boxes into masks for board outline, corrosion/burn areas, connectors, component cutouts, and repair-video tracking
- Implementation:
  - run SAM 2 on detector boxes and open-vocabulary proposals
  - store masks as label-review artifacts before YOLO retraining
  - use video masks to keep repair/playbook steps attached to the same part
- Risks:
  - large checkpoints increase install and inference cost
  - zero-shot masks still need human or metric validation before AOI use

### Grounding DINO
- Category: open_vocabulary_detector
- Lane: open_vocab_discovery
- URL: https://github.com/IDEA-Research/GroundingDINO
- Paper: https://arxiv.org/abs/2303.05499
- Benefit: finds unlabeled objects from text prompts such as battery connector, USB port, burnt capacitor, relay, heatsink, or corrosion
- Implementation:
  - generate prompt banks from repair/salvage case context
  - merge proposals with YOLO detections using conservative IoU rules
  - send high-confidence unknown objects into a review/autolabel queue
- Risks:
  - open-vocabulary labels can be semantically plausible but electrically wrong
  - must not overwrite measured detector classes without validation

### Microsoft Florence-2
- Category: vision_language_foundation_model
- Lane: caption_ocr_grounding
- URL: https://huggingface.co/microsoft/Florence-2-base
- Paper: https://arxiv.org/abs/2311.06242
- Benefit: adds dense captions, phrase grounding, OCR-style reading, and object-region context for unknown boards and machine parts
- Implementation:
  - use as a second opinion for case intake captions and label proposals
  - cross-check region text against OCR markings before suggesting datasheets
  - write proposals to evidence metadata instead of final detections
- Risks:
  - model-card task behavior is broad, not PCB-specific
  - outputs require grounding against measurements, markings, and known components

### PaddleOCR
- Category: ocr_foundation_toolkit
- Lane: marking_ocr
- URL: https://github.com/PaddlePaddle/PaddleOCR
- Benefit: improves IC marking, connector label, silkscreen, warning-label, and repair-manual text extraction beyond the current EasyOCR/Tesseract fallback
- Implementation:
  - add PaddleOCR as an optional OCR backend selected by availability
  - score OCR candidates by character whitelist, component crop quality, and datasheet hits
  - keep existing OCR fallback so the app runs without PaddlePaddle
- Risks:
  - PaddlePaddle install variants differ by CPU/GPU platform
  - tiny IC markings still require macro capture quality gates

### DINOv2 and CLIP few-shot embeddings
- Category: embedding_foundation_models
- Lane: few_shot_component_learning
- URL: https://github.com/facebookresearch/dinov2
- Paper: https://arxiv.org/abs/2304.07193
- Benefit: lets users teach rare modules from a few crops and reuse prototypes before a full detector retrain exists
- Implementation:
  - continue using FoundationLearner prototypes for rare components
  - gate prototype matches by crop quality and similarity thresholds
  - convert repeated high-confidence prototypes into YOLO training labels
- Risks:
  - embedding similarity is recognition, not pinout or circuit-function proof
  - prototype stores are model-version dependent

### X-AnyLabeling
- Category: annotation_tool
- Lane: human_in_loop_autolabeling
- URL: https://github.com/CVHub520/X-AnyLabeling
- Benefit: turns SAM/GroundingDINO-style proposals into reviewed labels for faster dataset growth
- Implementation:
  - export foundation proposals as annotation-review bundles
  - keep reviewer decisions as provenance for retraining
  - track label acceptance rate per source/model version
- Risks:
  - annotation tooling improves throughput, not model truth by itself
  - license and workflow fit must be reviewed before bundling

### Roboflow supervision
- Category: vision_dataset_tooling
- Lane: dataset_evaluation_and_visualization
- URL: https://github.com/roboflow/supervision
- Benefit: standardizes annotation transforms, visual QA, and detection/mask evaluation dashboards
- Implementation:
  - use for offline label QA and visual review scripts
  - do not make it required for API startup
  - write generated overlays under eval artifacts for review
- Risks:
  - dataset helper APIs change quickly
  - does not replace AOI-specific golden-reference metrics

## Non-Negotiable Claim Boundary

Open-vocabulary and vision-language outputs are assistive evidence until validated against labels, golden references, measurements, or datasheets.
