"""End-to-end salvage-to-product pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

import numpy as np
from PIL import Image

from src.core.ingest import CircuitAnalyzer
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine


class SalvageToProductPipeline:
    """Run image/listing ingestion through to build-package artifacts."""

    def __init__(
        self,
        analyzer: Any | None = None,
        workflow: SalvageWorkflowEngine | None = None,
    ):
        self.analyzer = analyzer or CircuitAnalyzer()
        self.workflow = workflow or SalvageWorkflowEngine()

    def run(
        self,
        images: Sequence[np.ndarray] | None = None,
        listings: Sequence[Dict[str, Any]] | None = None,
        *,
        backend: str | None = "hybrid",
        enable_ocr: bool = True,
        commit: bool = True,
        output_dir: str | Path | None = None,
    ) -> Dict[str, Any]:
        images = list(images or [])
        listings = list(listings or [])
        artifacts: Dict[str, Any] = {}
        analysis_payload: Dict[str, Any] | None = None
        market_context = {"listings": listings}

        if images:
            analysis_payload = self._analyze_images(images, backend=backend, enable_ocr=enable_ocr)
            artifacts["analysis"] = analysis_payload
            for analysis in self._analyses_for_workflow(analysis_payload):
                self.workflow.ingest_analysis(analysis, source="pipeline_scan", commit=commit)

        for listing in listings:
            self.workflow.ingest_listing(listing, commit=commit)

        final_report = self.workflow.plan_from_inventory(
            market_context=market_context if listings else None,
        )
        artifacts["workflow_report"] = final_report
        artifacts["build_package"] = final_report.get("build_package", {})
        artifacts["markdown_report"] = self.render_markdown(final_report, analysis_payload)

        if output_dir is not None:
            artifacts["artifact_paths"] = self.write_artifacts(artifacts, output_dir)

        return artifacts

    def run_from_paths(
        self,
        image_paths: Sequence[str | Path] | None = None,
        listing_paths: Sequence[str | Path] | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        images = [self._load_rgb(Path(path)) for path in (image_paths or [])]
        listings: List[Dict[str, Any]] = []
        for path in listing_paths or []:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, list):
                listings.extend(item for item in payload if isinstance(item, dict))
            elif isinstance(payload, dict):
                listings.append(payload)
        return self.run(images=images, listings=listings, **kwargs)

    def write_artifacts(self, artifacts: Dict[str, Any], output_dir: str | Path) -> Dict[str, str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            "workflow_report": out / "workflow_report.json",
            "build_package": out / "build_package.json",
            "markdown_report": out / "README.md",
        }
        if artifacts.get("analysis") is not None:
            paths["analysis"] = out / "analysis.json"

        for key, path in paths.items():
            if key == "markdown_report":
                path.write_text(str(artifacts.get(key, "")), encoding="utf-8")
            else:
                path.write_text(json.dumps(self._json_safe(artifacts.get(key, {})), indent=2), encoding="utf-8")
        return {key: str(path) for key, path in paths.items()}

    def render_markdown(
        self,
        workflow_report: Dict[str, Any],
        analysis_payload: Dict[str, Any] | None = None,
    ) -> str:
        decision = workflow_report.get("decision") or {}
        opportunity = (workflow_report.get("opportunity_report") or {}).get("best_opportunity") or {}
        package = workflow_report.get("build_package") or {}
        bom = package.get("bom") or {}
        validation = package.get("validation") or {}
        commercial = package.get("commercialization") or {}
        inventory = workflow_report.get("inventory") or {}

        lines = [
            "# Salvage-To-Product Report",
            "",
            f"Decision: **{decision.get('action', 'unknown')}**",
            f"Reason: {decision.get('reason', 'No reason available')}",
            f"Confidence: {decision.get('confidence', workflow_report.get('confidence', 0.0))}",
            "",
            "## Best Opportunity",
            f"- Name: {opportunity.get('name', 'None')}",
            f"- Type: {opportunity.get('type', 'none')}",
            f"- Score: {opportunity.get('score', 0.0)}",
            f"- Matched assets: {', '.join(opportunity.get('matched_assets', []) or []) or 'none'}",
            f"- Missing assets: {', '.join(opportunity.get('missing_assets', []) or []) or 'none'}",
            "",
            "## Build Package",
            f"- Package type: {package.get('package_type', 'none')}",
            f"- Target: {(package.get('target') or {}).get('name', 'none')}",
            f"- Required BOM: {', '.join(bom.get('required', []) or []) or 'none'}",
            f"- Owned BOM: {', '.join(bom.get('owned', []) or []) or 'none'}",
            f"- Missing BOM: {', '.join(bom.get('missing', []) or []) or 'none'}",
            "",
            "## Validation Gates",
        ]
        for item in validation.get("required_tests", []) or []:
            lines.append(f"- {item}")
        if not validation.get("required_tests"):
            lines.append("- collect more evidence before build")

        lines.extend(
            [
                "",
                "## Commercialization",
                f"- Positioning: {commercial.get('positioning', 'unknown')}",
                f"- Estimated low price: {commercial.get('estimated_market_price_low_usd')}",
                f"- Estimated high price: {commercial.get('estimated_market_price_high_usd')}",
                f"- Adjusted margin: {commercial.get('adjusted_margin_usd')}",
                "",
                "## Inventory",
                f"- Asset count: {inventory.get('asset_count', 0)}",
                f"- Estimated value: ${inventory.get('estimated_inventory_value_usd', 0.0)}",
                "",
                "## Source Analysis",
            ]
        )
        if analysis_payload:
            summary = analysis_payload.get("summary")
            if isinstance(summary, dict):
                lines.append(summary.get("summary_text", "Analysis summary unavailable."))
            else:
                lines.append(str(summary or "Analysis summary unavailable."))
        else:
            lines.append("No image analysis was supplied in this run.")
        lines.append("")
        return "\n".join(lines)

    def _analyze_images(
        self,
        images: Sequence[np.ndarray],
        backend: str | None,
        enable_ocr: bool,
    ) -> Dict[str, Any]:
        if len(images) == 1:
            result = self.analyzer.analyze_pcb(images[0], backend=backend, enable_ocr=enable_ocr)
            return {
                "mode": "single_image_pipeline_analysis",
                "results": result,
                "summary": self.analyzer.get_analysis_summary(result),
            }
        result = self.analyzer.analyze_board_set(list(images), backend=backend, enable_ocr=enable_ocr)
        return result

    def _analyses_for_workflow(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if payload.get("mode") == "single_image_pipeline_analysis":
            return [payload.get("results", {})]
        views = payload.get("views")
        if isinstance(views, list) and views:
            return [view for view in views if isinstance(view, dict)]
        fused = payload.get("fused_board_understanding")
        if isinstance(fused, dict):
            return [{"fused_board_understanding": fused}]
        return [payload]

    def _load_rgb(self, path: Path) -> np.ndarray:
        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"))

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return self._json_safe(value.tolist())
        return value
