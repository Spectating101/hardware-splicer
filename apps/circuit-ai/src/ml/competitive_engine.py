"""Competitive catch-up planning for Circuit-AI's repair/salvage vision stack.

This module is deliberately data/provenance focused. It does not pretend that a
downloaded checkpoint is production AOI; it tracks what each source can improve
and which local artifacts are present enough to train or evaluate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CompetitiveSource:
    """A dataset, competitor, or platform relevant to the target product scope."""

    source_id: str
    name: str
    category: str
    task: str
    url: str
    access: str
    license_note: str
    signal: str
    gap_closed: str
    priority: int
    local_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompetitorProfile:
    """A competing or adjacent product category."""

    profile_id: str
    name: str
    category: str
    url: str
    strengths: tuple[str, ...]
    circuit_ai_response: tuple[str, ...]


def source_registry() -> tuple[CompetitiveSource, ...]:
    """Return the current external/local source registry.

    The registry combines public datasets, local prepared datasets, and
    competitor references. Items are ordered by immediate practical priority.
    """

    return (
        CompetitiveSource(
            source_id="electrocom61_local",
            name="ElectroCom61 local YOLO corpus",
            category="dataset",
            task="component_detection",
            url="datasets/electrocom61/data.yaml",
            access="local",
            license_note="local prepared dataset; verify upstream license before redistribution",
            signal="multi-class electronic component boxes",
            gap_closed="improves component localization and class diversity beyond smoke checkpoints",
            priority=1,
            local_paths=(
                "datasets/electrocom61/data.yaml",
                "datasets/real_pcb_archive/data.yaml",
            ),
        ),
        CompetitiveSource(
            source_id="deeppcb",
            name="DeepPCB",
            category="dataset",
            task="golden_defect_detection",
            url="https://github.com/tangsanli5201/DeepPCB",
            access="public_git",
            license_note="research dataset; confirm downstream redistribution terms",
            signal="paired template/test PCB images with six defect classes",
            gap_closed="adds golden-reference defect localization and AOI-style evaluation",
            priority=1,
            local_paths=("datasets/deeppcb_subset/manifest.json",),
        ),
        CompetitiveSource(
            source_id="fpic",
            name="FICS PCB Image Collection / FPIC",
            category="dataset",
            task="component_detection",
            url="https://physicaldb.ece.ufl.edu/index.php/fics-pcb-image-collection-fpic/",
            access="request_or_download_page",
            license_note="academic dataset; follow site terms and attribution requirements",
            signal="PCB images and component annotations for real boards",
            gap_closed="improves generalization from synthetic/curated parts to real board photos",
            priority=2,
            local_paths=("datasets/fpic_yolo/data.yaml", "datasets/fpic_raw"),
        ),
        CompetitiveSource(
            source_id="hripcb",
            name="HRIPCB-style high-resolution PCB defect corpora",
            category="dataset",
            task="defect_detection",
            url="https://github.com/Charmve/Surface-Defect-Detection/tree/master/DeepPCB",
            access="public_or_mirrored",
            license_note="mirror availability varies; verify original dataset terms",
            signal="high-resolution defect samples for open, short, mousebite, spur, copper, pin-hole classes",
            gap_closed="broadens defect samples beyond a small DeepPCB subset",
            priority=3,
            local_paths=("datasets/hripcb",),
        ),
        CompetitiveSource(
            source_id="ifixit",
            name="iFixit",
            category="repair_platform",
            task="known_model_repair_guides",
            url="https://www.ifixit.com/",
            access="web_platform",
            license_note="do not copy guides; use as market/coverage reference and link-out inspiration only",
            signal="large repair-guide and parts ecosystem",
            gap_closed="sets the bar for model-specific repair breadth",
            priority=2,
        ),
        CompetitiveSource(
            source_id="daoai_aoi",
            name="DaoAI AOI",
            category="competitor",
            task="production_aoi",
            url="https://www.daoai.com/aoi",
            access="commercial",
            license_note="competitor reference only",
            signal="AI AOI positioning around CAD-free setup and factory defect classes",
            gap_closed="defines production AOI expectations for setup, defect classes, and false calls",
            priority=2,
        ),
        CompetitiveSource(
            source_id="delvitech_horus",
            name="Delvitech Horus",
            category="competitor",
            task="production_aoi",
            url="https://delvi.tech/technology/horus/",
            access="commercial",
            license_note="competitor reference only",
            signal="3D AOI/SPI, OCR, polarity, solder-joint inspection",
            gap_closed="defines the calibrated-inspection ceiling we should not overclaim against",
            priority=2,
        ),
        CompetitiveSource(
            source_id="flux_ai",
            name="Flux",
            category="competitor",
            task="ai_pcb_design",
            url="https://www.flux.ai/",
            access="commercial_saas",
            license_note="competitor reference only",
            signal="AI-assisted schematic/PCB design and collaboration",
            gap_closed="defines expectations for build/design UX after salvage modules are chosen",
            priority=3,
        ),
        CompetitiveSource(
            source_id="circuit_mind",
            name="Circuit Mind",
            category="competitor",
            task="ai_electronics_design",
            url="https://www.circuitmind.io/",
            access="commercial_saas",
            license_note="competitor reference only",
            signal="electronics design automation from requirements",
            gap_closed="sets expectations for requirements-to-schematic automation",
            priority=3,
        ),
    )


def competitor_profiles() -> tuple[CompetitorProfile, ...]:
    """Return adjacent competitor profiles and Circuit-AI's response strategy."""

    return (
        CompetitorProfile(
            profile_id="production_aoi",
            name="Production AOI platforms",
            category="factory_inspection",
            url="https://www.daoai.com/aoi",
            strengths=(
                "calibrated capture fixtures",
                "factory defect classes",
                "line integration and false-call reduction",
                "reference-board or CAD-assisted inspection",
            ),
            circuit_ai_response=(
                "do not overclaim production AOI without calibrated fixtures",
                "use DeepPCB/golden-reference evaluation for measured defect-localization progress",
                "position random-object repair/salvage reasoning as the differentiated layer",
            ),
        ),
        CompetitorProfile(
            profile_id="repair_guides",
            name="Repair-guide platforms",
            category="known_model_repair",
            url="https://www.ifixit.com/",
            strengths=(
                "large known-device guide library",
                "parts/tools ecosystem",
                "clear consumer repair UX",
            ),
            circuit_ai_response=(
                "win unknown-board intake and board-level diagnostic routing",
                "build model-specific packs only for strongest verticals first",
                "link evidence collection to measurements instead of generic advice",
            ),
        ),
        CompetitorProfile(
            profile_id="ai_pcb_design",
            name="AI PCB design platforms",
            category="new_design",
            url="https://www.flux.ai/",
            strengths=(
                "schematic/PCB creation from requirements",
                "collaboration and parts libraries",
                "design-for-manufacturing flow",
            ),
            circuit_ai_response=(
                "differentiate by starting from junk, broken devices, and recovered modules",
                "hand off salvage/build packages into KiCad/exportable design tools",
                "keep design automation downstream of evidence and safety validation",
            ),
        ),
        CompetitorProfile(
            profile_id="e_waste_marketplaces",
            name="E-waste and recommerce platforms",
            category="sourcing_resale",
            url="https://www.ewastetrader.com/",
            strengths=(
                "marketplace/logistics",
                "bulk sourcing and resale channels",
                "commercial transaction workflows",
            ),
            circuit_ai_response=(
                "score listings by recoverable module capability and build/resale value",
                "turn lots into test plans and build packages",
                "add marketplace integration only after reliable item-class coverage",
            ),
        ),
    )


def path_exists(root: Path, path: str) -> bool:
    return (root / path).exists()


def source_readiness(source: CompetitiveSource, root: Path | str = ".") -> dict[str, Any]:
    """Return local readiness for a source."""

    root_path = Path(root)
    existing = [path for path in source.local_paths if path_exists(root_path, path)]
    if not source.local_paths:
        status = "reference_only"
    elif len(existing) == len(source.local_paths):
        status = "ready"
    elif existing:
        status = "partial"
    elif source.access == "local":
        status = "missing_local"
    elif "request" in source.access:
        status = "needs_access"
    else:
        status = "needs_fetch"
    return {
        **asdict(source),
        "readiness": status,
        "existing_paths": existing,
        "missing_paths": [path for path in source.local_paths if path not in existing],
    }


def local_training_datasets(root: Path | str = ".") -> list[dict[str, Any]]:
    """Find YOLO data.yaml files that can be used for local training/eval."""

    root_path = Path(root)
    candidates: list[dict[str, Any]] = []
    for yaml_path in sorted(root_path.glob("datasets/**/data.yaml")):
        rel = yaml_path.relative_to(root_path)
        text = yaml_path.read_text(encoding="utf-8", errors="ignore")
        candidates.append(
            {
                "path": str(rel),
                "bytes": yaml_path.stat().st_size,
                "has_train": "train:" in text,
                "has_val": "val:" in text,
                "has_names": "names:" in text,
                "task": "component_detection",
            }
        )
    return candidates


def build_catchup_plan(root: Path | str = ".") -> dict[str, Any]:
    """Build a concrete catch-up plan from source readiness and local artifacts."""

    root_path = Path(root)
    readiness = [source_readiness(source, root_path) for source in source_registry()]
    training_datasets = local_training_datasets(root_path)
    deeppcb_ready = any(item["source_id"] == "deeppcb" and item["readiness"] == "ready" for item in readiness)
    component_dataset_ready = any(
        item["task"] == "component_detection" and item["has_train"] and item["has_val"] and item["has_names"]
        for item in training_datasets
    )

    immediate: list[dict[str, Any]] = []
    if component_dataset_ready:
        immediate.append(
            {
                "id": "fine_tune_component_detector",
                "lane": "component_detection",
                "why": "local YOLO datasets exist; smoke-ranked checkpoints can be replaced by measured mAP validation",
                "command": (
                    "python3 scripts/train_pcb_detector.py "
                    "--data-yaml datasets/electrocom61/data.yaml "
                    "--base-model models/pcb/pcb_components_yolo11n_thawed.pt "
                    "--epochs 50 --imgsz 640 --output-dir pcb_runs/competitive_component_v1"
                ),
            }
        )
    if deeppcb_ready:
        immediate.append(
            {
                "id": "expand_golden_defect_eval",
                "lane": "defect_detection",
                "why": "DeepPCB subset is available; expand sample count and track localization metrics",
                "command": (
                    "python3 scripts/fetch_deeppcb_subset.py --split test --limit 250 "
                    "--output-dir datasets/deeppcb_subset && "
                    "python3 scripts/evaluate_deeppcb_golden.py "
                    "--manifest datasets/deeppcb_subset/manifest.json "
                    "--output eval/deeppcb_golden_metrics.json"
                ),
            }
        )
    immediate.extend(
        [
            {
                "id": "capture_protocol",
                "lane": "production_aoi_readiness",
                "why": "competitors win with controlled capture; random photos need quality gates and guided retake prompts",
                "command": "document and enforce lighting/focus/angle retake gates in intake and scan flows",
            },
            {
                "id": "repair_packs",
                "lane": "repair_coverage",
                "why": "iFixit-style breadth must be verticalized; strong lanes need model-specific packs first",
                "command": "build packs for USB gadgets, retro handhelds/controllers, sensor/display modules",
            },
        ]
    )

    return {
        "goal": "competitive_unknown_electronics_intake_engine",
        "positioning": (
            "Start from an unknown item or listing, then route into repair, salvage, build, source/sell, "
            "safety review, or evidence collection."
        ),
        "sources": readiness,
        "competitors": [asdict(profile) for profile in competitor_profiles()],
        "local_training_datasets": training_datasets,
        "immediate_actions": immediate,
        "production_gates": {
            "component_detection": {"minimum_map50": 0.65, "target_map50": 0.80},
            "defect_detection": {"minimum_iou50_recall": 0.70, "target_iou50_recall": 0.90},
            "case_routing": {"minimum_human_acceptance": 0.80, "target_human_acceptance": 0.92},
            "safety": {"minimum_hazard_recall": 0.98, "target_hazard_recall": 0.995},
        },
    }


def markdown_report(plan: dict[str, Any]) -> str:
    """Render a compact Markdown report for humans."""

    lines = [
        "# Competitive Engine Catch-Up Plan",
        "",
        f"Goal: {plan['goal']}",
        "",
        plan["positioning"],
        "",
        "## Immediate Actions",
        "",
    ]
    for action in plan["immediate_actions"]:
        lines.extend(
            [
                f"### {action['id']}",
                f"- Lane: {action['lane']}",
                f"- Why: {action['why']}",
                f"- Command: `{action['command']}`",
                "",
            ]
        )

    lines.extend(["## Source Readiness", ""])
    for source in plan["sources"]:
        lines.extend(
            [
                f"### {source['name']}",
                f"- Task: {source['task']}",
                f"- Readiness: {source['readiness']}",
                f"- URL: {source['url']}",
                f"- Gap closed: {source['gap_closed']}",
                f"- License note: {source['license_note']}",
                "",
            ]
        )

    lines.extend(["## Production Gates", ""])
    for gate, values in plan["production_gates"].items():
        metrics = ", ".join(f"{key}: {value}" for key, value in values.items())
        lines.append(f"- {gate}: {metrics}")
    lines.append("")
    return "\n".join(lines)


def top_sources_by_priority(sources: Iterable[CompetitiveSource], limit: int = 3) -> list[CompetitiveSource]:
    return sorted(sources, key=lambda source: source.priority)[:limit]
