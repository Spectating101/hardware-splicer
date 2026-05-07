from __future__ import annotations

import json
import io
import os
import tempfile
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from loguru import logger
from PIL import Image
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.api.v1.auth import get_current_user
from src.api.v1.billing import router as billing_router
from src.api.v1.physics import router as physics_router
from src.core.ingest import CircuitAnalyzer
from src.engines.kicad_parser import KiCadParser
from src.intelligence.repair_encyclopedia import RepairEncyclopedia
from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
from src.intelligence.repair_lane_packs import RepairLanePacks
from src.intelligence.repair_market_coverage import RepairMarketCoverage
from src.intelligence.repair_value_trial_store import RepairValueTrialStore
from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder
from src.intelligence.salvage_workflow_engine import SalvageWorkflowEngine
from src.intelligence.salvage_pipeline import SalvageToProductPipeline
from src.intelligence.salvage_portfolio_planner import SalvagePortfolioPlanner
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner
from src.intelligence.board_session_store import BoardSessionStore
from src.ml.research_radar import build_research_integration_plan
from src.vision.foundation_adapters import build_foundation_assist_plan, foundation_backend_statuses


app = FastAPI(title="Circuit.AI API v1", version="1.0.0")
app.include_router(physics_router)
app.include_router(billing_router)
_analyzer: CircuitAnalyzer | None = None
_salvage_workflow: SalvageWorkflowEngine | None = None
_salvage_splice_planner: SalvageSplicePlanner | None = None
_salvage_portfolio_planner: SalvagePortfolioPlanner | None = None
_repair_encyclopedia: RepairEncyclopedia | None = None
_repair_case_evaluator: RepairCaseEvaluator | None = None
_repair_lane_packs: RepairLanePacks | None = None
_repair_coverage: RepairMarketCoverage | None = None
_repair_value_trials: RepairValueTrialStore | None = None
_repair_video_builder: RepairVideoPlaybookBuilder | None = None
_board_session_store: BoardSessionStore | None = None


def get_analyzer() -> CircuitAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = CircuitAnalyzer()
    return _analyzer


def get_salvage_workflow() -> SalvageWorkflowEngine:
    global _salvage_workflow
    if _salvage_workflow is None:
        _salvage_workflow = SalvageWorkflowEngine()
    return _salvage_workflow


def get_salvage_splice_planner() -> SalvageSplicePlanner:
    global _salvage_splice_planner
    if _salvage_splice_planner is None:
        _salvage_splice_planner = SalvageSplicePlanner()
    return _salvage_splice_planner


def get_salvage_portfolio_planner() -> SalvagePortfolioPlanner:
    global _salvage_portfolio_planner
    if _salvage_portfolio_planner is None:
        _salvage_portfolio_planner = SalvagePortfolioPlanner(get_salvage_splice_planner())
    return _salvage_portfolio_planner


def get_repair_encyclopedia() -> RepairEncyclopedia:
    global _repair_encyclopedia
    if _repair_encyclopedia is None:
        _repair_encyclopedia = RepairEncyclopedia()
    return _repair_encyclopedia


def get_repair_coverage() -> RepairMarketCoverage:
    global _repair_coverage
    if _repair_coverage is None:
        _repair_coverage = RepairMarketCoverage()
    return _repair_coverage


def get_repair_case_evaluator() -> RepairCaseEvaluator:
    global _repair_case_evaluator
    if _repair_case_evaluator is None:
        _repair_case_evaluator = RepairCaseEvaluator(
            encyclopedia=get_repair_encyclopedia(),
            coverage=get_repair_coverage(),
            playbook_builder=get_repair_video_builder(),
            session_store=get_board_session_store(),
        )
    return _repair_case_evaluator


def get_repair_lane_packs() -> RepairLanePacks:
    global _repair_lane_packs
    if _repair_lane_packs is None:
        _repair_lane_packs = RepairLanePacks()
    return _repair_lane_packs


def get_repair_value_trials() -> RepairValueTrialStore:
    global _repair_value_trials
    if _repair_value_trials is None:
        _repair_value_trials = RepairValueTrialStore(session_store=get_board_session_store())
    return _repair_value_trials


def get_repair_video_builder() -> RepairVideoPlaybookBuilder:
    global _repair_video_builder
    if _repair_video_builder is None:
        _repair_video_builder = RepairVideoPlaybookBuilder(get_repair_encyclopedia())
    return _repair_video_builder


def get_board_session_store() -> BoardSessionStore:
    global _board_session_store
    if _board_session_store is None:
        _board_session_store = BoardSessionStore()
    return _board_session_store


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/readyz")
def readyz(analyzer: CircuitAnalyzer = Depends(get_analyzer)) -> Dict[str, Any]:
    # "Ready" means the app can import and create its analyzer; the heavy
    # YOLO weights are lazily loaded per request.
    return {"ready": True, "backend_default": getattr(analyzer.detector, "default_backend", "unknown")}


@app.get("/ml/research-radar")
def ml_research_radar() -> Dict[str, Any]:
    return build_research_integration_plan(Path("."))


@app.get("/ml/foundation/status")
def ml_foundation_status(
    device_hint: Optional[str] = None,
    goal: str = "unknown_electronics_intake",
    has_video: bool = False,
) -> Dict[str, Any]:
    return {
        "backend_statuses": foundation_backend_statuses(),
        "assist_plan": build_foundation_assist_plan(
            device_hint=device_hint,
            has_video=has_video,
            goal=goal,
        ),
    }


@app.post("/analyze")
def analyze(
    file: UploadFile = File(...),
    backend: Optional[str] = Form(None),
    enable_ocr: bool = Form(True),
    reference_counts: Optional[str] = Form(None),
    reference_file: Optional[UploadFile] = File(None),
    golden_file: Optional[UploadFile] = File(None),
    reference_topology: Optional[str] = Form(None),
    reference_topology_file: Optional[UploadFile] = File(None),
    aoi_profile: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
) -> Dict[str, Any]:
    try:
        image_bytes = file.file.read()
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    reference_payload: Dict[str, int] = {}
    reference_topology_payload: Dict[str, Any] | None = None
    reference_image_payload: np.ndarray | None = None
    reference_sources: List[str] = []
    aoi_profile_payload: Dict[str, Any] = {}

    reference_counts_text = reference_counts if isinstance(reference_counts, str) else None
    if isinstance(reference_counts_text, str):
        reference_counts_text = reference_counts_text.strip()
        if reference_counts_text == "":
            reference_counts_text = None

    reference_topology_text = reference_topology if isinstance(reference_topology, str) else None
    if isinstance(reference_topology_text, str):
        reference_topology_text = reference_topology_text.strip()
        if reference_topology_text == "":
            reference_topology_text = None

    aoi_profile_text = aoi_profile if isinstance(aoi_profile, str) else None
    if isinstance(aoi_profile_text, str):
        aoi_profile_text = aoi_profile_text.strip()
        if aoi_profile_text == "":
            aoi_profile_text = None

    def _has_upload(file_item: Any) -> bool:
        return isinstance(file_item, StarletteUploadFile) and bool((file_item.filename or "").strip())

    legacy_reference_file = _has_upload(reference_file)
    structured_inputs = [
        reference_counts_text is not None,
        _has_upload(golden_file),
        reference_topology_text is not None,
        _has_upload(reference_topology_file),
    ]
    if legacy_reference_file and any(structured_inputs):
        raise HTTPException(
            status_code=400,
            detail="Use reference_file alone, or combine reference_counts, golden_file, and reference_topology separately",
        )

    def _parse_counts_payload(raw_counts: Any) -> Dict[str, int]:
        if not isinstance(raw_counts, dict):
            raise HTTPException(
                status_code=400,
                detail="reference payload must be a JSON object mapping component names to counts",
            )
        parsed: Dict[str, int] = {}
        for name, raw_count in raw_counts.items():
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue
            if count > 0:
                parsed[str(name)] = count
        return parsed

    def _parse_reference_file(file_item: UploadFile) -> tuple[Dict[str, int], Dict[str, Any] | None, np.ndarray | None]:
        reference_bytes = file_item.file.read()
        if not reference_bytes:
            raise HTTPException(status_code=400, detail="Reference file is empty")

        content_type = (file_item.content_type or "").lower()
        filename = (file_item.filename or "").lower()
        is_json = (
            filename.endswith(".json")
            or "application/json" in content_type
            or content_type.startswith("text/")
        )

        if is_json:
            try:
                raw_reference = json.loads(reference_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid reference JSON file: {e}")
            if isinstance(raw_reference, dict) and {"nets", "components"}.issubset(set(raw_reference.keys())):
                return {}, raw_reference, None
            return _parse_counts_payload(raw_reference), None, None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
                tmp.write(reference_bytes)
                tmp_path = tmp.name
            parsed = KiCadParser(tmp_path).parse()
            if not isinstance(parsed, dict) or not parsed.get("nets"):
                raise ValueError("Not a KiCad netlist")
            return {}, parsed, None
        except HTTPException:
            raise
        except Exception:
            # Legacy behavior fallback: treat as image and run component count AOI.
            try:
                reference_image = Image.open(io.BytesIO(reference_bytes))
                reference_np = np.array(reference_image)
                reference_detections = analyzer.detector.detect_components(
                    reference_np,
                    backend=backend,
                    enable_ocr=enable_ocr,
                )
                parsed_counts: Dict[str, int] = {}
                for det in reference_detections:
                    name = str(det.get("class_name", "unknown"))
                    parsed_counts[name] = parsed_counts.get(name, 0) + 1
                return parsed_counts, None, reference_np
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Could not parse reference file: {e}")
        finally:
            if tmp_path is not None:
                os.remove(tmp_path)

    def _parse_golden_file(file_item: UploadFile) -> np.ndarray:
        reference_bytes = file_item.file.read()
        if not reference_bytes:
            raise HTTPException(status_code=400, detail="Golden reference file is empty")
        try:
            reference_image = Image.open(io.BytesIO(reference_bytes)).convert("RGB")
            return np.array(reference_image)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not parse golden reference image: {e}")

    if reference_counts_text is not None:
        try:
            reference_payload = _parse_counts_payload(json.loads(reference_counts_text))
            reference_sources.append("counts_json")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid reference_counts JSON: {e}")

    if reference_topology_text is not None:
        try:
            raw_reference_topology = json.loads(reference_topology_text)
            if (
                isinstance(raw_reference_topology, dict)
                and {"nets", "components"}.issubset(set(raw_reference_topology.keys()))
            ):
                reference_topology_payload = raw_reference_topology
                reference_sources.append("topology_json")
            else:
                reference_payload = _parse_counts_payload(raw_reference_topology)
                reference_sources.append("counts_from_topology_json")
        except json.JSONDecodeError:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
                    tmp.write(reference_topology_text.encode("utf-8"))
                    tmp_path = tmp.name
                parsed = KiCadParser(tmp_path).parse()
                if not isinstance(parsed, dict) or not parsed.get("nets"):
                    raise ValueError("Not a KiCad netlist")
                reference_topology_payload = parsed
                reference_sources.append("topology_text")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid reference_topology text: {e}")
            finally:
                if tmp_path is not None:
                    os.remove(tmp_path)

    if _has_upload(reference_topology_file):
        parsed_counts, parsed_topology, parsed_image = _parse_reference_file(reference_topology_file)
        if parsed_topology is not None:
            reference_topology_payload = parsed_topology
            reference_sources.append("topology_file")
        elif parsed_counts:
            reference_payload = parsed_counts
            reference_sources.append("counts_from_topology_file")
        elif parsed_image is not None:
            reference_image_payload = parsed_image
            reference_sources.append("golden_from_topology_file")

    if _has_upload(golden_file):
        reference_image_payload = _parse_golden_file(golden_file)
        reference_sources.append("golden_file")

    if legacy_reference_file:
        reference_payload, reference_topology_payload, reference_image_payload = _parse_reference_file(reference_file)
        reference_sources.append(
            "topology_file"
            if reference_topology_payload is not None
            else "image"
            if reference_image_payload is not None
            else "counts_file"
        )

    if aoi_profile_text is not None:
        try:
            raw_profile = json.loads(aoi_profile_text)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid aoi_profile JSON: {e}")
        if not isinstance(raw_profile, dict):
            raise HTTPException(status_code=400, detail="aoi_profile must be a JSON object")
        aoi_profile_payload = raw_profile

    analyzer_signature = inspect.signature(analyzer.analyze_pcb)
    analyze_kwargs: Dict[str, Any] = {
        "backend": backend,
        "enable_ocr": enable_ocr,
    }
    if "reference_counts" in analyzer_signature.parameters:
        analyze_kwargs["reference_counts"] = reference_payload
    if "reference_topology" in analyzer_signature.parameters:
        analyze_kwargs["reference_topology"] = reference_topology_payload
    if "reference_image" in analyzer_signature.parameters:
        analyze_kwargs["reference_image"] = reference_image_payload
    if "aoi_profile" in analyzer_signature.parameters:
        analyze_kwargs["aoi_profile"] = aoi_profile_payload

    try:
        results = analyzer.analyze_pcb(image_np, **analyze_kwargs)
    except TypeError as e:
        # Backward-compatible fallback for older/an alternative analyzer mocks.
        if "reference_counts" in str(e) or "reference_topology" in str(e) or "aoi_profile" in str(e):
            results = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
        else:
            raise
    summary = analyzer.get_analysis_summary(results)

    analysis_meta = results.get("analysis_metadata", {}) if isinstance(results, dict) else {}
    detection_summary = results.get("detection_summary", {}) if isinstance(results, dict) else {}
    certainty_ledger = results.get("certainty_ledger", {}) if isinstance(results, dict) else {}
    detection_quality = (
        analysis_meta.get("detection_quality")
        or detection_summary.get("detection_quality")
        or "unknown"
    )

    logger.info(
        f"/analyze user={current_user.get('user_id')} backend={backend or analysis_meta.get('backend')} ocr={enable_ocr}"
    )
    return {
        "results": results,
        "summary": summary,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "detection_quality": detection_quality,
            "detection_summary": detection_summary,
            "backend": analysis_meta.get("backend") or backend,
            "ocr": analysis_meta.get("ocr") if "ocr" in analysis_meta else enable_ocr,
            "certainty": {
                "score": analysis_meta.get("certainty_score") or (certainty_ledger.get("overall") or {}).get("score"),
                "level": analysis_meta.get("certainty_level") or (certainty_ledger.get("overall") or {}).get("level"),
                "missing_evidence_count": analysis_meta.get("missing_evidence_count", len(certainty_ledger.get("missing_evidence", []) or [])),
                "training_capture_recommended": analysis_meta.get(
                    "training_capture_recommended",
                    bool((certainty_ledger.get("training_queue") or {}).get("should_capture")),
                ),
            },
            "production_aoi": {
                "disposition": analysis_meta.get("production_aoi_disposition"),
                "release_authorized": analysis_meta.get("production_aoi_release_authorized", False),
                "certainty_score": analysis_meta.get("production_aoi_certainty_score"),
                "certainty_level": analysis_meta.get("production_aoi_certainty_level"),
            },
            "reference": {
                "status": analysis_meta.get("reference_aoi_status"),
                "component_delta": analysis_meta.get("reference_component_delta", 0),
                "topology_status": analysis_meta.get("topology_aoi_status"),
                "topology_delta": analysis_meta.get("topology_aoi_delta", 0),
                "golden_status": analysis_meta.get("golden_aoi_status"),
                "golden_defect_count": analysis_meta.get("golden_defect_count", 0),
                "input": {
                    "counts": reference_payload,
                    "reference_source": "+".join(reference_sources) if reference_sources else "none",
                    "topology": bool(reference_topology_payload),
                    "golden_image": bool(reference_image_payload is not None),
                    "aoi_profile": bool(aoi_profile_payload),
                },
            },
        },
    }


@app.post("/analyze/multiview")
def analyze_multiview(
    files: List[UploadFile] = File(...),
    backend: Optional[str] = Form(None),
    enable_ocr: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
) -> Dict[str, Any]:
    images: List[np.ndarray] = []
    filenames: List[str] = []
    for file in files:
        try:
            image_bytes = file.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            images.append(np.array(image))
            filenames.append(file.filename or "upload")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image {file.filename}: {e}")

    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    if hasattr(analyzer, "analyze_board_set"):
        results = analyzer.analyze_board_set(images, backend=backend, enable_ocr=enable_ocr)
        summary = results.get("summary", "")
    else:
        first = analyzer.analyze_pcb(images[0], backend=backend, enable_ocr=enable_ocr)
        results = {"mode": "single_view_fallback", "views": [first], "fused_board_understanding": first.get("board_understanding", {})}
        summary = analyzer.get_analysis_summary(first)

    fused = results.get("fused_board_understanding", {}) if isinstance(results, dict) else {}
    logger.info(
        f"/analyze/multiview user={current_user.get('user_id')} files={len(images)} backend={backend} ocr={enable_ocr}"
    )
    return {
        "results": results,
        "summary": summary,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "filenames": filenames,
            "view_count": len(images),
            "backend": backend,
            "ocr": enable_ocr,
            "fused_board_type": (fused.get("board_identity") or {}).get("primary_type"),
            "fused_confidence": fused.get("confidence", (fused.get("board_identity") or {}).get("confidence", 0.0)),
        },
    }


@app.get("/board-sessions")
def board_sessions_list(
    status: Optional[str] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    sessions = store.list_sessions(status=status, limit=limit)
    return {
        "sessions": sessions,
        "metadata": {"user_id": current_user.get("user_id"), "count": len(sessions)},
    }


@app.post("/board-sessions")
def board_sessions_create(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    session = store.create_session(
        payload,
        user_id=str(current_user.get("user_id") or "anonymous"),
        commit=commit,
    )
    return {
        "session": session,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.post("/board-sessions/from-scan")
def board_sessions_create_from_scan(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    device_hint: Optional[str] = Form(None),
    symptoms: Optional[str] = Form(None),
    route: Optional[str] = Form(None),
    backend: Optional[str] = Form("hybrid"),
    enable_ocr: bool = Form(True),
    commit: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    try:
        image_bytes = file.file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    analysis = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
    summary = analyzer.get_analysis_summary(analysis)
    session = store.create_session(
        {
            "description": description or "",
            "device_hint": device_hint or "",
            "symptoms": _parse_symptoms(symptoms),
            "route": route,
            "analysis": analysis,
            "summary": summary,
            "source": "scan_upload",
        },
        user_id=str(current_user.get("user_id") or "anonymous"),
        commit=commit,
    )

    capture = None
    if commit:
        safe_name = _safe_evidence_filename(file.filename or "scan.png")
        evidence_dir = store.root_dir / str(session["session_id"]) / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        image_path = evidence_dir / safe_name
        image_path.write_bytes(image_bytes)
        capture_result = store.attach_capture(
            str(session["session_id"]),
            {
                "kind": "primary_scan",
                "filename": file.filename or safe_name,
                "path": str(image_path),
                "content_type": file.content_type,
                "size_bytes": len(image_bytes),
            },
            commit=True,
        )
        session = capture_result.get("session", session)
        capture = capture_result.get("capture")

    return {
        "session": session,
        "analysis": analysis,
        "summary": summary,
        "capture": capture,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "committed": commit,
            "backend": backend,
            "ocr": enable_ocr,
        },
    }


@app.get("/board-sessions/review-queue")
def board_sessions_review_queue(
    status: str = "open",
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    tasks = store.review_queue(status=status, limit=limit)
    return {
        "tasks": tasks,
        "metadata": {"user_id": current_user.get("user_id"), "count": len(tasks), "status": status},
    }


@app.get("/board-sessions/benchmark")
def board_sessions_benchmark(
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    return {
        "benchmark": store.benchmark_report(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/board-sessions/aoi-calibration")
def board_sessions_aoi_calibration(
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    return {
        "calibration": store.aoi_calibration_report(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/board-sessions/{session_id}")
def board_sessions_get(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Board session not found: {session_id}")
    return {
        "session": session,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/board-sessions/{session_id}/evidence-graph")
def board_sessions_evidence_graph(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    graph = store.evidence_graph(session_id)
    if "error" in graph:
        raise HTTPException(status_code=404, detail=graph["error"])
    return {
        "graph": graph,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/board-sessions/{session_id}/dossier")
def board_sessions_dossier(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    dossier = store.dossier(session_id)
    if "error" in dossier:
        raise HTTPException(status_code=404, detail=dossier["error"])
    return {
        "dossier": dossier,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/board-sessions/{session_id}/captures")
def board_sessions_add_capture(
    session_id: str,
    file: Optional[UploadFile] = File(None),
    kind: Optional[str] = Form("evidence"),
    notes: Optional[str] = Form(None),
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Board session not found: {session_id}")

    filename = None
    path = None
    content_type = None
    size_bytes = None
    if file is not None and (file.filename or "").strip():
        evidence_bytes = file.file.read()
        filename = file.filename or "evidence.bin"
        safe_name = _safe_evidence_filename(filename)
        evidence_dir = store.root_dir / session_id / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path_obj = evidence_dir / safe_name
        path_obj.write_bytes(evidence_bytes)
        path = str(path_obj)
        content_type = file.content_type
        size_bytes = len(evidence_bytes)

    result = store.attach_capture(
        session_id,
        {
            "kind": kind or "evidence",
            "filename": filename,
            "path": path,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "notes": notes,
        },
        commit=commit,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.post("/board-sessions/{session_id}/review")
def board_sessions_review_task(
    session_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    result = store.review_task(
        session_id,
        {**payload, "reviewer": payload.get("reviewer") or current_user.get("user_id")},
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/board-sessions/{session_id}/measurement")
def board_sessions_add_measurement(
    session_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    result = store.add_measurement(session_id, payload)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/board-sessions/{session_id}/outcome")
def board_sessions_record_outcome(
    session_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    result = store.record_outcome(session_id, payload)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/board-sessions/{session_id}/training-export")
def board_sessions_training_export(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    result = store.export_training_package(session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/salvage/workflow")
def salvage_workflow_plan(
    current_user: Dict[str, Any] = Depends(get_current_user),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    report = workflow.plan_from_inventory()
    return {
        "report": report,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/salvage/build-package")
def salvage_build_package(
    current_user: Dict[str, Any] = Depends(get_current_user),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    report = workflow.plan_from_inventory()
    return {
        "build_package": report.get("build_package", {}),
        "decision": report.get("decision", {}),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/salvage/splice-plan")
def salvage_splice_plan(
    payload: Dict[str, Any],
    commit_session: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    plan = planner.plan(payload)
    session = None
    if commit_session:
        session_payload = plan.get("session_payload") if isinstance(plan.get("session_payload"), dict) else {}
        session = store.create_session(
            session_payload,
            user_id=str(current_user.get("user_id") or "anonymous"),
            commit=True,
        )
    return {
        "splice_plan": plan,
        "session": session,
        "metadata": {"user_id": current_user.get("user_id"), "committed_session": bool(session)},
    }


@app.post("/salvage/splice-case")
def salvage_splice_case(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    plan = planner.plan(payload)
    session_payload = plan.get("session_payload") if isinstance(plan.get("session_payload"), dict) else {}
    session = store.create_session(
        session_payload,
        user_id=str(current_user.get("user_id") or "anonymous"),
        commit=commit,
    )
    return {
        "splice_plan": plan,
        "session": session,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.post("/salvage/portfolio-plan")
def salvage_portfolio_plan(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvagePortfolioPlanner = Depends(get_salvage_portfolio_planner),
) -> Dict[str, Any]:
    plan = planner.plan(payload)
    return {
        "portfolio_plan": plan,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/salvage/pipeline")
def salvage_pipeline(
    files: Optional[List[UploadFile]] = File(None),
    listings: Optional[str] = Form(None),
    backend: Optional[str] = Form("hybrid"),
    enable_ocr: bool = Form(True),
    commit: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    images: List[np.ndarray] = []
    filenames: List[str] = []
    for file in files or []:
        if not file or not (file.filename or "").strip():
            continue
        try:
            image_bytes = file.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            images.append(np.array(image))
            filenames.append(file.filename or "upload")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image {file.filename}: {e}")

    listing_payloads: List[Dict[str, Any]] = []
    if listings:
        try:
            raw = json.loads(listings)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid listings JSON: {e}")
        raw_items = raw if isinstance(raw, list) else [raw]
        listing_payloads = [item for item in raw_items if isinstance(item, dict)]

    if not images and not listing_payloads:
        raise HTTPException(status_code=400, detail="Supply at least one image or listing")

    pipeline = SalvageToProductPipeline(analyzer=analyzer, workflow=workflow)
    result = pipeline.run(
        images=images,
        listings=listing_payloads,
        backend=backend,
        enable_ocr=enable_ocr,
        commit=commit,
    )
    return {
        "workflow_report": result.get("workflow_report", {}),
        "build_package": result.get("build_package", {}),
        "markdown_report": result.get("markdown_report", ""),
        "metadata": {
            "user_id": current_user.get("user_id"),
            "filenames": filenames,
            "listing_count": len(listing_payloads),
            "committed": commit,
        },
    }


@app.post("/salvage/analysis")
def salvage_ingest_analysis(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    analysis = payload.get("results") if isinstance(payload.get("results"), dict) else payload
    result = workflow.ingest_analysis(
        analysis,
        source=str(payload.get("source") or "api_analysis"),
        commit=commit,
    )
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.post("/salvage/listing")
def salvage_ingest_listing(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    result = workflow.ingest_listing(payload, commit=commit)
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.post("/salvage/assets/{asset_id}/test")
def salvage_record_test_result(
    asset_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    workflow: SalvageWorkflowEngine = Depends(get_salvage_workflow),
) -> Dict[str, Any]:
    result = workflow.record_test_result(
        asset_id,
        test_status=str(payload.get("test_status") or "tested"),
        condition=payload.get("condition"),
        notes=payload.get("notes"),
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
        "metadata": {"user_id": current_user.get("user_id")},
    }


def _parse_symptoms(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
            if isinstance(decoded, str):
                return [decoded.strip()] if decoded.strip() else []
        except json.JSONDecodeError:
            pass
        separators = ["\n", ";", ","]
        values = [raw]
        for separator in separators:
            if separator in raw:
                values = raw.split(separator)
                break
        return [item.strip() for item in values if item.strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def _safe_evidence_filename(filename: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
    safe = safe.strip("._") or "evidence"
    return safe[:120]


@app.post("/repair/guide")
def repair_guide(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    encyclopedia: RepairEncyclopedia = Depends(get_repair_encyclopedia),
) -> Dict[str, Any]:
    analysis = payload.get("analysis") or payload.get("results") or {}
    guide = encyclopedia.generate(
        analysis=analysis if isinstance(analysis, dict) else {},
        symptoms=_parse_symptoms(payload.get("symptoms")),
        device_hint=payload.get("device_hint"),
    )
    return {
        "repair_guide": guide,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/repair/pipeline")
def repair_pipeline(
    file: Optional[UploadFile] = File(None),
    symptoms: Optional[str] = Form(None),
    device_hint: Optional[str] = Form(None),
    backend: Optional[str] = Form("hybrid"),
    enable_ocr: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    analyzer: CircuitAnalyzer = Depends(get_analyzer),
    encyclopedia: RepairEncyclopedia = Depends(get_repair_encyclopedia),
) -> Dict[str, Any]:
    analysis: Dict[str, Any] = {}
    summary = ""
    filename = None
    if file and (file.filename or "").strip():
        try:
            image_bytes = file.file.read()
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            image_np = np.array(image)
            filename = file.filename or "upload"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}")
        analysis = analyzer.analyze_pcb(image_np, backend=backend, enable_ocr=enable_ocr)
        summary = analyzer.get_analysis_summary(analysis)

    guide = encyclopedia.generate(
        analysis=analysis,
        symptoms=_parse_symptoms(symptoms),
        device_hint=device_hint,
    )
    return {
        "analysis": analysis,
        "summary": summary,
        "repair_guide": guide,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "filename": filename,
            "backend": backend,
            "ocr": enable_ocr,
        },
    }


@app.get("/repair/coverage")
def repair_coverage_portfolio(
    current_user: Dict[str, Any] = Depends(get_current_user),
    coverage: RepairMarketCoverage = Depends(get_repair_coverage),
) -> Dict[str, Any]:
    return {
        "coverage": coverage.portfolio(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/repair/coverage")
def repair_coverage_query(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    coverage: RepairMarketCoverage = Depends(get_repair_coverage),
) -> Dict[str, Any]:
    query = str(payload.get("query") or payload.get("text") or "")
    return {
        "coverage": coverage.evaluate_text(query),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/repair/video-playbook")
def repair_video_playbook(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    builder: RepairVideoPlaybookBuilder = Depends(get_repair_video_builder),
) -> Dict[str, Any]:
    video_reference = payload.get("video_reference") if isinstance(payload.get("video_reference"), dict) else payload
    analysis = payload.get("analysis") or payload.get("results") or {}
    playbook = builder.build(
        video_reference=video_reference if isinstance(video_reference, dict) else {},
        analysis=analysis if isinstance(analysis, dict) else {},
        symptoms=_parse_symptoms(payload.get("symptoms")),
        device_hint=payload.get("device_hint"),
    )
    return {
        "playbook": playbook,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/repair/case-eval")
def repair_case_eval(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    evaluator: RepairCaseEvaluator = Depends(get_repair_case_evaluator),
) -> Dict[str, Any]:
    raw_cases = payload.get("cases")
    if isinstance(raw_cases, list):
        cases = [item for item in raw_cases if isinstance(item, dict)]
    else:
        cases = [payload]
    report = evaluator.evaluate_cases(
        cases,
        commit_sessions=bool(payload.get("commit_sessions", False)),
    )
    return {
        "case_eval": report,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/repair/lane-packs")
def repair_lane_packs_list(
    current_user: Dict[str, Any] = Depends(get_current_user),
    packs: RepairLanePacks = Depends(get_repair_lane_packs),
) -> Dict[str, Any]:
    return {
        "lane_packs": packs.list_packs(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/repair/lane-packs/match")
def repair_lane_packs_match(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    packs: RepairLanePacks = Depends(get_repair_lane_packs),
) -> Dict[str, Any]:
    text = str(payload.get("text") or payload.get("query") or payload.get("description") or "")
    return {
        "match": packs.match(text),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/repair/lane-packs/{lane_id}")
def repair_lane_packs_get(
    lane_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    packs: RepairLanePacks = Depends(get_repair_lane_packs),
) -> Dict[str, Any]:
    pack = packs.get_pack(lane_id)
    if not pack:
        raise HTTPException(status_code=404, detail=f"Repair lane pack not found: {lane_id}")
    return {
        "lane_pack": pack,
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.get("/repair/value-trials")
def repair_value_trials_list(
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user),
    trials: RepairValueTrialStore = Depends(get_repair_value_trials),
) -> Dict[str, Any]:
    rows = trials.list_trials(limit=limit)
    return {
        "value_trials": rows,
        "metadata": {"user_id": current_user.get("user_id"), "count": len(rows)},
    }


@app.post("/repair/value-trials")
def repair_value_trials_create(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    trials: RepairValueTrialStore = Depends(get_repair_value_trials),
) -> Dict[str, Any]:
    trial = trials.create_trial(
        payload,
        user_id=str(current_user.get("user_id") or "anonymous"),
        commit=commit,
    )
    return {
        "value_trial": trial,
        "metadata": {"user_id": current_user.get("user_id"), "committed": commit},
    }


@app.get("/repair/value-trials/benchmark")
def repair_value_trials_benchmark(
    current_user: Dict[str, Any] = Depends(get_current_user),
    trials: RepairValueTrialStore = Depends(get_repair_value_trials),
) -> Dict[str, Any]:
    return {
        "benchmark": trials.benchmark_report(),
        "metadata": {"user_id": current_user.get("user_id")},
    }
