"""Research radar for foundation-model upgrades to Circuit-AI.

This file is intentionally dependency-light. It records which outside research
and tooling lanes should influence the product, then turns them into a concrete
integration plan that can be surfaced in docs, eval artifacts, and APIs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ResearchSource:
    """A primary source or tool that can improve the inspection engine."""

    source_id: str
    name: str
    category: str
    url: str
    primary_reference: str
    integration_lane: str
    optional_backend_id: str
    expected_benefit: str
    implementation: tuple[str, ...]
    risks: tuple[str, ...]
    priority: int
    local_contracts: tuple[str, ...] = ()
    paper_url: str = ""


@dataclass(frozen=True)
class IntegrationLane:
    """A product lane that combines research sources into a practical feature."""

    lane_id: str
    name: str
    goal: str
    sources: tuple[str, ...]
    repo_entrypoints: tuple[str, ...]
    next_steps: tuple[str, ...]
    production_gate: str


def research_source_registry() -> tuple[ResearchSource, ...]:
    """Return source-backed model/tool candidates ordered by practical priority."""

    return (
        ResearchSource(
            source_id="yolo11",
            name="Ultralytics YOLO11",
            category="production_detector",
            url="https://docs.ultralytics.com/models/yolo11/",
            primary_reference="official_docs",
            integration_lane="production_component_detection",
            optional_backend_id="ultralytics",
            expected_benefit=(
                "keeps the narrow PCB/component detector fast enough for AOI-style batch scoring "
                "and deployable edge inference"
            ),
            implementation=(
                "continue using scripts/train_pcb_detector.py for measured fine-tunes",
                "promote only checkpoints with validation mAP and sample-level error cards",
                "use foundation proposals as auto-label candidates, not as production truth",
            ),
            risks=(
                "generic COCO checkpoints are not PCB detectors",
                "CPU training smoke tests prove the path, not production quality",
            ),
            priority=1,
            local_contracts=("scripts/train_pcb_detector.py", "src/vision/detector.py"),
        ),
        ResearchSource(
            source_id="sam2",
            name="Meta Segment Anything Model 2",
            category="segmentation_foundation_model",
            url="https://github.com/facebookresearch/sam2",
            primary_reference="official_github",
            integration_lane="component_masks_and_video_tracking",
            optional_backend_id="sam2",
            expected_benefit=(
                "turns boxes into masks for board outline, corrosion/burn areas, connectors, "
                "component cutouts, and repair-video tracking"
            ),
            implementation=(
                "run SAM 2 on detector boxes and open-vocabulary proposals",
                "store masks as label-review artifacts before YOLO retraining",
                "use video masks to keep repair/playbook steps attached to the same part",
            ),
            risks=(
                "large checkpoints increase install and inference cost",
                "zero-shot masks still need human or metric validation before AOI use",
            ),
            priority=1,
            local_contracts=("src/vision/foundation_adapters.py", "src/vision/golden_reference.py"),
            paper_url="https://arxiv.org/abs/2408.00714",
        ),
        ResearchSource(
            source_id="grounding_dino",
            name="Grounding DINO",
            category="open_vocabulary_detector",
            url="https://github.com/IDEA-Research/GroundingDINO",
            primary_reference="official_github",
            integration_lane="open_vocab_discovery",
            optional_backend_id="grounding_dino",
            expected_benefit=(
                "finds unlabeled objects from text prompts such as battery connector, USB port, "
                "burnt capacitor, relay, heatsink, or corrosion"
            ),
            implementation=(
                "generate prompt banks from repair/salvage case context",
                "merge proposals with YOLO detections using conservative IoU rules",
                "send high-confidence unknown objects into a review/autolabel queue",
            ),
            risks=(
                "open-vocabulary labels can be semantically plausible but electrically wrong",
                "must not overwrite measured detector classes without validation",
            ),
            priority=1,
            local_contracts=("src/vision/foundation_adapters.py", "src/intelligence/salvage_pipeline.py"),
            paper_url="https://arxiv.org/abs/2303.05499",
        ),
        ResearchSource(
            source_id="florence2",
            name="Microsoft Florence-2",
            category="vision_language_foundation_model",
            url="https://huggingface.co/microsoft/Florence-2-base",
            primary_reference="official_model_card",
            integration_lane="caption_ocr_grounding",
            optional_backend_id="florence2",
            expected_benefit=(
                "adds dense captions, phrase grounding, OCR-style reading, and object-region "
                "context for unknown boards and machine parts"
            ),
            implementation=(
                "use as a second opinion for case intake captions and label proposals",
                "cross-check region text against OCR markings before suggesting datasheets",
                "write proposals to evidence metadata instead of final detections",
            ),
            risks=(
                "model-card task behavior is broad, not PCB-specific",
                "outputs require grounding against measurements, markings, and known components",
            ),
            priority=2,
            local_contracts=("src/vision/foundation_adapters.py", "src/vision/ocr_engine.py"),
            paper_url="https://arxiv.org/abs/2311.06242",
        ),
        ResearchSource(
            source_id="paddleocr",
            name="PaddleOCR",
            category="ocr_foundation_toolkit",
            url="https://github.com/PaddlePaddle/PaddleOCR",
            primary_reference="official_github",
            integration_lane="marking_ocr",
            optional_backend_id="paddleocr",
            expected_benefit=(
                "improves IC marking, connector label, silkscreen, warning-label, and repair-manual "
                "text extraction beyond the current EasyOCR/Tesseract fallback"
            ),
            implementation=(
                "add PaddleOCR as an optional OCR backend selected by availability",
                "score OCR candidates by character whitelist, component crop quality, and datasheet hits",
                "keep existing OCR fallback so the app runs without PaddlePaddle",
            ),
            risks=(
                "PaddlePaddle install variants differ by CPU/GPU platform",
                "tiny IC markings still require macro capture quality gates",
            ),
            priority=2,
            local_contracts=("src/vision/ocr_engine.py",),
        ),
        ResearchSource(
            source_id="dinov2_clip",
            name="DINOv2 and CLIP few-shot embeddings",
            category="embedding_foundation_models",
            url="https://github.com/facebookresearch/dinov2",
            primary_reference="official_github",
            integration_lane="few_shot_component_learning",
            optional_backend_id="transformers",
            expected_benefit=(
                "lets users teach rare modules from a few crops and reuse prototypes before a full "
                "detector retrain exists"
            ),
            implementation=(
                "continue using FoundationLearner prototypes for rare components",
                "gate prototype matches by crop quality and similarity thresholds",
                "convert repeated high-confidence prototypes into YOLO training labels",
            ),
            risks=(
                "embedding similarity is recognition, not pinout or circuit-function proof",
                "prototype stores are model-version dependent",
            ),
            priority=2,
            local_contracts=("src/vision/foundation_learner.py",),
            paper_url="https://arxiv.org/abs/2304.07193",
        ),
        ResearchSource(
            source_id="x_anylabeling",
            name="X-AnyLabeling",
            category="annotation_tool",
            url="https://github.com/CVHub520/X-AnyLabeling",
            primary_reference="official_github",
            integration_lane="human_in_loop_autolabeling",
            optional_backend_id="x_anylabeling",
            expected_benefit=(
                "turns SAM/GroundingDINO-style proposals into reviewed labels for faster dataset growth"
            ),
            implementation=(
                "export foundation proposals as annotation-review bundles",
                "keep reviewer decisions as provenance for retraining",
                "track label acceptance rate per source/model version",
            ),
            risks=(
                "annotation tooling improves throughput, not model truth by itself",
                "license and workflow fit must be reviewed before bundling",
            ),
            priority=3,
            local_contracts=("datasets/", "eval/competitive_engine/"),
        ),
        ResearchSource(
            source_id="supervision",
            name="Roboflow supervision",
            category="vision_dataset_tooling",
            url="https://github.com/roboflow/supervision",
            primary_reference="official_github",
            integration_lane="dataset_evaluation_and_visualization",
            optional_backend_id="supervision",
            expected_benefit=(
                "standardizes annotation transforms, visual QA, and detection/mask evaluation dashboards"
            ),
            implementation=(
                "use for offline label QA and visual review scripts",
                "do not make it required for API startup",
                "write generated overlays under eval artifacts for review",
            ),
            risks=(
                "dataset helper APIs change quickly",
                "does not replace AOI-specific golden-reference metrics",
            ),
            priority=3,
            local_contracts=("scripts/benchmark_pcb_models.py", "scripts/evaluate_deeppcb_golden.py"),
        ),
    )


def integration_lanes() -> tuple[IntegrationLane, ...]:
    """Return the practical lanes that compose the next engine version."""

    return (
        IntegrationLane(
            lane_id="production_component_detection",
            name="Production component detector",
            goal="make YOLO checkpoints measurably better on PCB/component datasets",
            sources=("yolo11", "dinov2_clip"),
            repo_entrypoints=("src/vision/detector.py", "scripts/train_pcb_detector.py"),
            next_steps=(
                "train 50+ epoch GPU runs on ElectroCom61 plus reviewed auto-labels",
                "promote best.pt only after validation mAP, confusion, and sample cards pass",
                "keep classical CV fallback for low-confidence scans",
            ),
            production_gate="mAP50 >= 0.65 before beta, mAP50 >= 0.80 before AOI claims",
        ),
        IntegrationLane(
            lane_id="open_vocab_discovery",
            name="Open-vocabulary discovery",
            goal="notice useful unlabeled parts on random electronics and e-commerce listings",
            sources=("grounding_dino", "florence2", "sam2"),
            repo_entrypoints=("src/vision/foundation_adapters.py", "src/intelligence/salvage_pipeline.py"),
            next_steps=(
                "generate prompt banks from device hints, symptoms, and salvage goals",
                "write candidate boxes/masks into evidence metadata with source attribution",
                "route unknown useful parts into teach-component and annotation-review flows",
            ),
            production_gate="human label acceptance >= 70% for auto-label candidates before retraining",
        ),
        IntegrationLane(
            lane_id="mask_and_video_tracking",
            name="Mask and repair-video tracking",
            goal="attach repair steps and defects to exact regions instead of loose boxes",
            sources=("sam2",),
            repo_entrypoints=("src/vision/golden_reference.py", "src/intelligence/repair_video_playbook.py"),
            next_steps=(
                "use detector/open-vocab boxes as mask prompts",
                "persist masks for defects, connectors, corrosion, and board outline",
                "track repeated part instances across video frames for playbook generation",
            ),
            production_gate="mask IoU >= 0.70 on reviewed defect/component masks",
        ),
        IntegrationLane(
            lane_id="marking_ocr",
            name="Marking and label OCR",
            goal="turn tiny markings into datasheet, safety, and repair evidence",
            sources=("paddleocr", "florence2"),
            repo_entrypoints=("src/vision/ocr_engine.py", "src/vision/detector.py"),
            next_steps=(
                "add optional PaddleOCR backend behind existing OCR interface",
                "score text by crop quality and datasheet search consistency",
                "surface uncertain markings as review tasks instead of definitive IDs",
            ),
            production_gate="top marking string exact/normalized match >= 75% on reviewed crop set",
        ),
        IntegrationLane(
            lane_id="human_in_loop_dataset_growth",
            name="Human-in-loop dataset growth",
            goal="convert every good scan, repair case, and listing into training/eval assets",
            sources=("x_anylabeling", "supervision", "grounding_dino", "sam2"),
            repo_entrypoints=("eval/competitive_engine/", "datasets/", "scripts/benchmark_pcb_models.py"),
            next_steps=(
                "emit review bundles from foundation proposals",
                "track acceptance rate, rejected labels, and retraining impact",
                "separate production labels from exploratory suggestions",
            ),
            production_gate="new labels improve validation mAP/recall without increasing false positives",
        ),
    )


def build_research_integration_plan(root: Path | str = ".") -> dict[str, Any]:
    """Build a source-backed plan for next model integrations."""

    root_path = Path(root)
    sources = [asdict(source) for source in research_source_registry()]
    lanes = [asdict(lane) for lane in integration_lanes()]

    local_contracts: dict[str, dict[str, Any]] = {}
    for source in research_source_registry():
        checks = []
        for path in source.local_contracts:
            checks.append({"path": path, "exists": (root_path / path).exists()})
        local_contracts[source.source_id] = {"contracts": checks}

    return {
        "goal": "research_backed_foundation_assist_for_aoi_repair_salvage",
        "principle": (
            "Use foundation models to propose regions, labels, masks, text, and training data; "
            "use measured detectors, golden references, and human review for production truth."
        ),
        "sources": sources,
        "lanes": lanes,
        "local_contracts": local_contracts,
        "default_pipeline": (
            "polish_image -> YOLO/classical detections -> OCR -> foundation proposals if available -> "
            "mask/caption/marking evidence -> human review/autolabel queue -> measured retraining"
        ),
        "do_not_overclaim": (
            "Open-vocabulary and vision-language outputs are assistive evidence until validated "
            "against labels, golden references, measurements, or datasheets."
        ),
    }


def markdown_report(plan: dict[str, Any]) -> str:
    """Render the research plan as compact Markdown."""

    lines = [
        "# Research Tech Radar",
        "",
        f"Goal: {plan['goal']}",
        "",
        plan["principle"],
        "",
        "## Default Pipeline",
        "",
        plan["default_pipeline"],
        "",
        "## Integration Lanes",
        "",
    ]

    for lane in plan["lanes"]:
        lines.extend(
            [
                f"### {lane['name']}",
                f"- Lane: {lane['lane_id']}",
                f"- Goal: {lane['goal']}",
                f"- Sources: {', '.join(lane['sources'])}",
                f"- Entrypoints: {', '.join(lane['repo_entrypoints'])}",
                f"- Gate: {lane['production_gate']}",
                "- Next steps:",
            ]
        )
        for step in lane["next_steps"]:
            lines.append(f"  - {step}")
        lines.append("")

    lines.extend(["## Source Radar", ""])
    for source in plan["sources"]:
        lines.extend(
            [
                f"### {source['name']}",
                f"- Category: {source['category']}",
                f"- Lane: {source['integration_lane']}",
                f"- URL: {source['url']}",
                *([f"- Paper: {source['paper_url']}"] if source.get("paper_url") else []),
                f"- Benefit: {source['expected_benefit']}",
                "- Implementation:",
            ]
        )
        for step in source["implementation"]:
            lines.append(f"  - {step}")
        lines.append("- Risks:")
        for risk in source["risks"]:
            lines.append(f"  - {risk}")
        lines.append("")

    lines.extend(["## Non-Negotiable Claim Boundary", "", plan["do_not_overclaim"], ""])
    return "\n".join(lines)


def top_research_sources(sources: Iterable[ResearchSource], limit: int = 4) -> list[ResearchSource]:
    """Return the highest-priority research sources."""

    return sorted(sources, key=lambda source: source.priority)[:limit]
