from __future__ import annotations

import io
import json
import os
import tempfile
import inspect
import time
import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from PIL import Image
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile

from src.api.v1.auth import get_current_user
from src.api.v1.billing import router as billing_router
from src.api.v1.metrics import (
    get_metrics_response,
    record_error_metrics,
    record_request_metrics,
    set_active_connections,
)
from src.api.v1.physics import router as physics_router
from src.core.ingest import CircuitAnalyzer
from src.engines.board_intelligence import (
    analyze_board_intelligence,
    analyze_board_session_intelligence,
    assess_downstream_capabilities,
)
from src.engines.circuit_board_graph import analyze_circuit_design, analyze_circuit_session
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
from src.intelligence.functional_salvage_workflow import FunctionalSalvageWorkflowRunner
from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner, circuit_ai_model_status
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.bench_topology_capture import (
    bench_capture_to_topology_evidence,
    build_bench_capture_template,
    enrich_payload_with_bench_topology_capture,
    extract_bench_topology_capture,
)
from src.intelligence.authority_ledger import build_authority_ledger
from src.intelligence.board_omniscience_map import build_board_omniscience_map
from src.intelligence.hardware_plan import HardwarePlanOrchestrator
from src.intelligence.design_test_kit import build_design_test_kit
from src.intelligence.diy_project_engineer import build_diy_project_engineering_plan
from src.intelligence.diy_project_session import DIYProjectSessionStore
from src.intelligence.field_model_advisory import build_field_model_advisory
from src.intelligence.field_operator_agent import build_field_operator_next_action
from src.intelligence.measurement_authority_closure import build_measurement_authority_closure
from src.intelligence.measurement_session_progress import build_measurement_session_progress
from src.intelligence.multiview_board_evidence import fuse_board_photo_set
from src.intelligence.production_casefile import build_production_casefile
from src.intelligence.resource_strategy import build_resource_strategy
from src.intelligence.topology_netlist_compiler import compile_topology_to_netlist
from src.intelligence.visual_topology_hypothesis import build_visual_topology_hypothesis
from src.ml.research_radar import build_research_integration_plan
from src.vision.foundation_adapters import build_foundation_assist_plan, foundation_backend_statuses
from src.vision.qwen_board_vision import (
    DEFAULT_MAX_TOKENS as QWEN_DEFAULT_MAX_TOKENS,
    analyze_board_image_with_qwen,
    qwen_vision_status,
)


app = FastAPI(title="Circuit.AI API v1", version="1.0.0")
app.include_router(physics_router)
app.include_router(billing_router)


class BatchAnalysisRequest(BaseModel):
    image_paths: List[str]
    analysis_options: Dict[str, Any] = {}


class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]


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
_diy_project_session_store: DIYProjectSessionStore | None = None


@lru_cache(maxsize=1)
def get_enhanced_analyzer():
    from src.core.enhanced_analyzer import enhanced_analyzer

    return enhanced_analyzer


@lru_cache(maxsize=1)
def get_websocket_manager():
    from src.services.websocket_service import websocket_manager

    return websocket_manager


@lru_cache(maxsize=1)
def get_cache_service():
    from src.services.cache_service import cache_service

    return cache_service


@lru_cache(maxsize=1)
def get_queue_service():
    from src.services.queue_service import queue_service

    return queue_service


@lru_cache(maxsize=1)
def get_kicad_parser():
    from src.intelligence.parser import KiCadParser as LegacyKiCadParser

    return LegacyKiCadParser


@lru_cache(maxsize=1)
def get_circuit_parser_analyzer():
    from src.intelligence.analyzer import CircuitAnalyzer as NetlistCircuitAnalyzer

    return NetlistCircuitAnalyzer


@lru_cache(maxsize=1)
def get_bom_generator():
    from src.intelligence.bom import BomGenerator

    return BomGenerator


@lru_cache(maxsize=1)
def get_workflow_engine():
    from src.engines.unified_workflow import UnifiedWorkflowEngine

    return UnifiedWorkflowEngine()


def _format_validation_workflow_response(result: Any, kicad_path: str) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "status": result.status,
        "next_steps": result.next_steps,
    }

    issues = result.validation_issues or []
    critical = [i for i in issues if getattr(i, "severity", None) == "critical"]
    errors = [i for i in issues if getattr(i, "severity", None) == "error"]
    warnings = [i for i in issues if getattr(i, "severity", None) == "warning"]

    response["validation"] = {
        "issues_count": len(issues),
        "critical": len(critical),
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": [
            {
                "severity": getattr(i, "severity", "unknown"),
                "component": getattr(i, "component", None),
                "issue": getattr(i, "issue", None),
                "solution": getattr(i, "solution", None),
                "physics": getattr(i, "physics", None),
            }
            for i in issues
        ],
    }

    if issues:
        response["manufacturing_ready"] = (
            False if result.status == "validation_partial" else (len(critical) == 0 and len(errors) == 0)
        )
    else:
        response["manufacturing_ready"] = result.status not in {"error", "validation_failed"}

    if str(kicad_path).lower().endswith(".kicad_pcb"):
        try:
            from src.engines.kicad_pcb_geometry import extract_pcb_geometry

            response["pcb_geometry"] = extract_pcb_geometry(str(kicad_path))
        except Exception:
            pass

    return response


@app.middleware("http")
async def instrumentation_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        record_error_metrics(type(exc).__name__, request.url.path)
        raise
    finally:
        duration = time.perf_counter() - start
        record_request_metrics(request.url.path, request.method, status_code, duration)


@app.on_event("startup")
async def enhanced_surface_startup():
    try:
        queue_service = get_queue_service()
        cache_service = get_cache_service()
        queue_service.start_workers()
        logger.info("Queue workers started")
        cache_service.cleanup_expired()
        logger.info("Cache cleanup completed")
        logger.info("Enhanced API startup completed")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def enhanced_surface_shutdown():
    try:
        get_queue_service().stop_workers()
        logger.info("Queue workers stopped")
    except Exception as e:
        logger.error(f"Queue shutdown error: {e}")
    try:
        websocket_manager = get_websocket_manager()
        for client_id in list(websocket_manager.active_connections.keys()):
            websocket_manager.disconnect(client_id)
        set_active_connections(0)
        logger.info("WebSocket connections closed")
        logger.info("Enhanced API shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


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


def get_diy_project_session_store() -> DIYProjectSessionStore:
    global _diy_project_session_store
    if _diy_project_session_store is None:
        _diy_project_session_store = DIYProjectSessionStore()
    return _diy_project_session_store


@app.get("/healthz")
def healthz() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/readyz")
def readyz(analyzer: CircuitAnalyzer = Depends(get_analyzer)) -> Dict[str, Any]:
    # "Ready" means the app can import and create its analyzer; the heavy
    # YOLO weights are lazily loaded per request.
    return {"ready": True, "backend_default": getattr(analyzer.detector, "default_backend", "unknown")}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    websocket_manager = get_websocket_manager()
    await websocket_manager.connect(websocket, client_id)
    set_active_connections(len(websocket_manager.active_connections))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "subscribe_analysis":
                analysis_id = message.get("analysis_id")
                if analysis_id:
                    await websocket_manager.subscribe_to_analysis(client_id, analysis_id)
                    await websocket_manager.send_personal_message(
                        {"type": "subscription_confirmed", "analysis_id": analysis_id},
                        client_id,
                    )

            elif message.get("type") == "unsubscribe_analysis":
                analysis_id = message.get("analysis_id")
                if analysis_id:
                    await websocket_manager.unsubscribe_from_analysis(client_id, analysis_id)
                    await websocket_manager.send_personal_message(
                        {"type": "unsubscription_confirmed", "analysis_id": analysis_id},
                        client_id,
                    )

            elif message.get("type") == "ping":
                await websocket_manager.send_personal_message(
                    {"type": "pong", "timestamp": datetime.now().isoformat()},
                    client_id,
                )

    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        set_active_connections(len(websocket_manager.active_connections))
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        websocket_manager.disconnect(client_id)
        set_active_connections(len(websocket_manager.active_connections))


@app.get("/")
async def root():
    return {
        "message": "Circuit.AI Enhanced Component Intelligence Platform",
        "version": "2.1.0",
        "features": [
            "Real-time WebSocket analysis progress",
            "Enhanced computer vision with multi-model ensemble",
            "Advanced LLM-powered functionality mapping",
            "Netlist Analysis (ERC)",
            "BOM Generation",
            "Intelligent project recommendations",
            "Educational content generation",
            "Repair recommendations",
            "Advanced caching and job queuing",
            "Batch processing capabilities",
        ],
        "endpoints": {
            "analyze": "/analyze - Upload PCB image for enhanced analysis",
            "analyze_netlist": "/analyze/netlist - Upload KiCad netlist for ERC",
            "generate_bom": "/generate/bom - Upload KiCad netlist for BOM CSV",
            "batch_analyze": "/batch_analyze - Submit batch analysis job",
            "job_status": "/job/{job_id} - Get batch job status",
            "websocket": "/ws/{client_id} - Real-time WebSocket connection",
            "health": "/health - Enhanced system health check",
            "metrics": "/metrics - Prometheus metrics for enhanced API monitoring",
            "statistics": "/statistics - Comprehensive system statistics",
            "cache_stats": "/cache/stats - Cache performance statistics",
            "queue_stats": "/queue/stats - Job queue statistics",
            "websocket_stats": "/ws/stats - WebSocket connection statistics",
        },
    }


@app.post("/analyze/netlist")
async def analyze_netlist(file: UploadFile = File(...)):
    try:
        content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            parser_cls = get_kicad_parser()
            analyzer_cls = get_circuit_parser_analyzer()
            parser = parser_cls(tmp_path)
            data = parser.parse()
            analyzer = analyzer_cls(data)

            stats = analyzer.get_stats()
            floating_nets = analyzer.find_single_node_nets()

            return {
                "status": "success",
                "stats": stats,
                "issues": {
                    "floating_nets": floating_nets,
                    "count": len(floating_nets),
                },
                "passed": len(floating_nets) == 0,
            }
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Netlist analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/bom")
async def generate_bom(file: UploadFile = File(...)):
    try:
        content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".net") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            parser_cls = get_kicad_parser()
            bom_generator_cls = get_bom_generator()
            parser = parser_cls(tmp_path)
            data = parser.parse()
            bom_gen = bom_generator_cls(data)
            csv_content = bom_gen.generate_csv()

            return StreamingResponse(
                io.StringIO(csv_content),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=bom.csv"},
            )
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"BOM generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_analyze")
async def batch_analyze(request: BatchAnalysisRequest):
    try:
        job_id = get_enhanced_analyzer().submit_batch_analysis_job(
            request.image_paths,
            **request.analysis_options,
        )

        return {
            "job_id": job_id,
            "status": "submitted",
            "image_count": len(request.image_paths),
            "submitted_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Batch analysis submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    try:
        status = get_enhanced_analyzer().get_batch_job_status(job_id)
        return status

    except Exception as e:
        logger.error(f"Job status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    try:
        health = get_enhanced_analyzer().get_system_health()
        return health

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/statistics")
async def get_statistics():
    try:
        stats = get_enhanced_analyzer().get_analysis_statistics()
        return stats

    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats")
async def get_cache_stats():
    try:
        stats = get_cache_service().get_stats()
        return stats

    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/stats")
async def get_queue_stats():
    try:
        stats = get_queue_service().get_queue_stats()
        return stats

    except Exception as e:
        logger.error(f"Queue stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ws/stats")
async def get_websocket_stats():
    try:
        websocket_manager = get_websocket_manager()
        set_active_connections(len(websocket_manager.active_connections))
        stats = websocket_manager.get_connection_stats()
        return stats

    except Exception as e:
        logger.error(f"WebSocket stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
async def clear_cache(pattern: Optional[str] = None):
    try:
        deleted_count = get_cache_service().clear(pattern)
        return {
            "message": "Cache cleared successfully",
            "deleted_entries": deleted_count,
            "pattern": pattern,
        }

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/components")
async def get_component_database():
    try:
        enhanced_analyzer = get_enhanced_analyzer()
        return {
            "total_components": len(enhanced_analyzer.mapper.component_database),
            "component_types": list(enhanced_analyzer.mapper.component_database.keys()),
            "last_updated": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Component database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/projects")
async def get_project_templates():
    try:
        projects = get_enhanced_analyzer().mapper.project_templates
        return {
            "total_projects": len(projects),
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "difficulty": p.difficulty,
                    "category": p.category,
                    "estimated_cost": p.estimated_cost,
                    "score": p.score,
                }
                for p in projects
            ],
        }

    except Exception as e:
        logger.error(f"Project templates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/educational")
async def get_educational_content():
    try:
        content = get_enhanced_analyzer().mapper.educational_content
        return {
            "total_content": len(content),
            "content": [
                {
                    "title": c.title,
                    "difficulty": c.difficulty,
                    "component_type": c.component_type,
                    "estimated_time": c.estimated_time,
                }
                for c in content.values()
            ],
        }

    except Exception as e:
        logger.error(f"Educational content error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/repair")
async def get_repair_guides():
    try:
        guides = get_enhanced_analyzer().mapper.repair_guides
        return {
            "total_guides": len(guides),
            "guides": [
                {
                    "component_type": g.component_type,
                    "issue": g.issue,
                    "difficulty": g.difficulty,
                    "success_rate": g.success_rate,
                }
                for g in guides.values()
            ],
        }

    except Exception as e:
        logger.error(f"Repair guides error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    return get_metrics_response()


@app.post("/validate-kicad")
async def validate_kicad_proxy(
    kicad_file: UploadFile = File(...),
    hints: Optional[str] = Form(None),
):
    logger.info(f"Received KiCad validation request: {kicad_file.filename}")

    content = await kicad_file.read()
    temp_path = f"/tmp/{uuid.uuid4()}.kicad_pcb"
    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        result = get_workflow_engine().execute_validation_workflow(kicad_file=str(temp_path))
        return JSONResponse(_format_validation_workflow_response(result, temp_path))
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/api/proxy/health")
async def health_check_proxy():
    return {"status": "ok", "service": "circuit-ai-backend"}


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


@app.get("/vision/qwen/status")
def qwen_board_vision_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "status": qwen_vision_status(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/vision/qwen/board-evidence")
def qwen_board_vision_evidence(
    file: UploadFile = File(...),
    goal: Optional[str] = Form(None),
    device_hint: Optional[str] = Form(None),
    symptoms: Optional[str] = Form(None),
    live: bool = Form(False),
    include_hardware_plan: bool = Form(True),
    max_tokens: int = Form(QWEN_DEFAULT_MAX_TOKENS),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        image_bytes = file.file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image upload: {exc}")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image upload is empty")

    result = analyze_board_image_with_qwen(
        image_bytes,
        filename=file.filename or "board.png",
        media_type=file.content_type,
        goal=goal or "",
        device_hint=device_hint or "",
        symptoms=_parse_symptoms(symptoms),
        live=live,
        max_tokens=max_tokens,
    )
    evidence = result.get("board_evidence") if isinstance(result.get("board_evidence"), dict) else {}
    plan = None
    if include_hardware_plan and evidence:
        plan = HardwarePlanOrchestrator().plan(
            {
                "goal": goal or "reason about Qwen board evidence",
                "device_hint": device_hint or "",
                "symptoms": _parse_symptoms(symptoms),
                "strategy_mode": "constrained",
                "board_evidence": evidence,
                "use_reference_catalog": False,
            }
        )
    return {
        "qwen_board_vision": result,
        "board_evidence": evidence,
        "vision_evidence_bridge": result.get("vision_evidence_bridge") if isinstance(result.get("vision_evidence_bridge"), dict) else {},
        "hardware_plan": plan,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "live": live,
            "include_hardware_plan": include_hardware_plan,
        },
    }


@app.post("/vision/board-evidence/fuse")
def fuse_multiview_board_evidence(
    payload: Dict[str, Any],
    include_hardware_plan: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    reconstruction = fuse_board_photo_set(payload or {})
    evidence = reconstruction.get("board_evidence") if isinstance(reconstruction.get("board_evidence"), dict) else {}
    plan = None
    if include_hardware_plan and evidence:
        plan = HardwarePlanOrchestrator().plan(
            {
                **(payload or {}),
                "goal": (payload or {}).get("goal") or "reconstruct board evidence from multiple photos",
                "strategy_mode": (payload or {}).get("strategy_mode") or "constrained",
                "board_evidence": evidence,
                "use_reference_catalog": bool((payload or {}).get("use_reference_catalog", False)),
            }
        )
    return {
        "multiview_board_reconstruction": reconstruction,
        "board_evidence": evidence,
        "vision_evidence_bridge": reconstruction.get("vision_evidence_bridge")
        if isinstance(reconstruction.get("vision_evidence_bridge"), dict)
        else {},
        "hardware_plan": plan,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "include_hardware_plan": include_hardware_plan,
            "fixed_view_slots_required": False,
        },
    }


@app.post("/vision/board-evidence/visual-topology")
def visual_topology_hypothesis(
    payload: Dict[str, Any],
    include_hardware_plan: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    hypothesis = build_visual_topology_hypothesis(payload or {})
    plan = HardwarePlanOrchestrator().plan(payload or {}) if include_hardware_plan else None
    return {
        "visual_topology_hypothesis": hypothesis,
        "hardware_plan": plan,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "include_hardware_plan": include_hardware_plan,
            "candidate_only": True,
        },
    }


@app.post("/hardware/topology-capture/template")
def hardware_topology_capture_template(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    body = payload or {}
    reference = (
        body.get("topology_evidence")
        if isinstance(body.get("topology_evidence"), dict)
        else body.get("reference_topology")
    )
    template = build_bench_capture_template(
        reference_topology=reference if isinstance(reference, dict) else None,
        board_evidence=body.get("board_evidence") if isinstance(body.get("board_evidence"), dict) else None,
    )
    return {
        "bench_topology_capture_template": template,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "reference_seed_is_not_evidence": True,
        },
    }


@app.post("/hardware/topology-capture/convert")
def hardware_topology_capture_convert(
    payload: Dict[str, Any],
    include_hardware_plan: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    body = payload or {}
    capture = extract_bench_topology_capture(body) or body
    reference = (
        body.get("topology_evidence")
        if isinstance(body.get("topology_evidence"), dict)
        else body.get("reference_topology")
    )
    topology_evidence = bench_capture_to_topology_evidence(
        capture,
        reference_topology=reference if isinstance(reference, dict) else None,
    )
    enriched = enrich_payload_with_bench_topology_capture(body)
    plan = HardwarePlanOrchestrator().plan(enriched) if include_hardware_plan else None
    return {
        "bench_topology_capture": capture,
        "topology_evidence": topology_evidence,
        "enriched_payload": enriched,
        "hardware_plan": plan,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "include_hardware_plan": include_hardware_plan,
            "measurement_capture_required_for_authority": True,
        },
    }


@app.post("/hardware/measurement-authority/close")
def hardware_measurement_authority_close(
    payload: Dict[str, Any],
    include_casefile: bool = True,
    include_omniscience: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    closure = build_measurement_authority_closure(
        payload or {},
        include_casefile=bool(include_casefile),
        include_omniscience=bool(include_omniscience),
    )
    after = closure.get("authority_after") if isinstance(closure.get("authority_after"), dict) else {}
    delta = closure.get("authority_delta") if isinstance(closure.get("authority_delta"), dict) else {}
    return {
        "measurement_authority_closure": closure,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "current_authority_level": after.get("current_authority_level"),
            "authority_score": after.get("authority_score"),
            "score_delta": delta.get("score_delta"),
            "next_action_id": (closure.get("next_action") or {}).get("action_id")
            if isinstance(closure.get("next_action"), dict)
            else None,
        },
    }


@app.post("/hardware/measurement-session/progress")
def hardware_measurement_session_progress(
    payload: Dict[str, Any],
    include_authority_closure: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    progress = build_measurement_session_progress(
        payload or {},
        include_authority_closure=bool(include_authority_closure),
    )
    summary = progress.get("progress") if isinstance(progress.get("progress"), dict) else {}
    next_measurement = progress.get("next_measurement") if isinstance(progress.get("next_measurement"), dict) else {}
    return {
        "measurement_session_progress": progress,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "status": progress.get("status"),
            "progress_score": summary.get("progress_score"),
            "open_count": summary.get("open_count"),
            "authority_packet_ready": summary.get("authority_packet_ready"),
            "next_action_id": next_measurement.get("action_id"),
        },
    }


@app.post("/hardware/topology-netlist/compile")
def hardware_topology_netlist_compile(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    compiled = compile_topology_to_netlist(payload or {})
    coverage = compiled.get("coverage") if isinstance(compiled.get("coverage"), dict) else {}
    return {
        "topology_netlist_compilation": compiled,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "available": bool(compiled.get("available")),
            "source": compiled.get("source"),
            "coverage_score": coverage.get("score"),
            "simulation_ready": coverage.get("simulation_ready"),
        },
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


@app.post("/board-sessions/{session_id}/analysis")
def board_sessions_append_analysis(
    session_id: str,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else payload.get("results")
    if not isinstance(analysis, dict) or not analysis:
        raise HTTPException(status_code=400, detail="analysis object is required")
    result = store.append_analysis(
        session_id,
        analysis,
        source=str(payload.get("source") or "manual_analysis"),
        summary=payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "result": result,
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


@app.post("/board-intelligence/analyze-design")
def board_intelligence_analyze_design(
    payload: Dict[str, Any],
    commit_session: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    try:
        intelligence = analyze_board_intelligence(payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    session = None
    if commit_session:
        session = store.create_session(
            {
                "description": payload.get("description") or "Circuit-AI board intelligence analysis",
                "route": "board_intelligence",
                "analysis": intelligence,
                "summary": {
                    "overall_disposition": intelligence.get("overall_disposition"),
                    "board_count": intelligence.get("board_count"),
                },
                "source": "design_evidence",
            },
            user_id=str(current_user.get("user_id") or "anonymous"),
            commit=True,
        )

    return {
        "status": "success",
        "intelligence": intelligence,
        "session": session,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "committed": bool(commit_session),
        },
    }


@app.post("/board-intelligence/sessions/{session_id}/analyze")
def board_intelligence_analyze_session(
    session_id: str,
    payload: Optional[Dict[str, Any]] = None,
    commit_analysis: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Board session not found: {session_id}")

    body = payload or {}
    try:
        intelligence = analyze_board_session_intelligence(
            session,
            design_payload=body.get("design") if isinstance(body.get("design"), dict) else None,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    saved = None
    if commit_analysis:
        saved = store.append_analysis(
            session_id,
            intelligence,
            source="board_intelligence_session",
            summary={
                "overall_disposition": intelligence.get("overall_disposition"),
                "readiness_level": (intelligence.get("readiness") or {}).get("level"),
                "coverage_score": (intelligence.get("evidence_coverage") or {}).get("score"),
            },
            commit=True,
        )
        if "error" in saved:
            raise HTTPException(status_code=404, detail=saved["error"])

    return {
        "status": "success",
        "intelligence": intelligence,
        "saved": saved,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "committed": bool(commit_analysis),
        },
    }


@app.get("/board-intelligence/downstream-capabilities")
def board_intelligence_downstream_capabilities(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "status": "success",
        "capabilities": assess_downstream_capabilities(),
        "metadata": {"user_id": current_user.get("user_id")},
    }


@app.post("/circuit/boards/analyze-design")
def circuit_boards_analyze_design(
    payload: Dict[str, Any],
    commit_session: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    try:
        circuit = analyze_circuit_design(payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    session = None
    if commit_session:
        session = store.create_session(
            {
                "description": payload.get("description") or "Circuit graph and splice contract",
                "route": "circuit",
                "analysis": circuit,
                "summary": {
                    "overall_readiness": circuit.get("overall_readiness"),
                    "board_count": circuit.get("board_count"),
                },
                "source": "circuit_design",
            },
            user_id=str(current_user.get("user_id") or "anonymous"),
            commit=True,
        )

    return {
        "status": "success",
        "circuit": circuit,
        "session": session,
        "metadata": {"user_id": current_user.get("user_id"), "committed": bool(commit_session)},
    }


@app.post("/circuit/sessions/{session_id}/advance")
def circuit_sessions_advance(
    session_id: str,
    payload: Optional[Dict[str, Any]] = None,
    commit_analysis: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Board session not found: {session_id}")
    body = payload or {}
    try:
        circuit = analyze_circuit_session(
            session,
            design_payload=body.get("design") if isinstance(body.get("design"), dict) else None,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    saved = None
    if commit_analysis:
        saved = store.append_analysis(
            session_id,
            circuit,
            source="circuit_session_advance",
            summary={
                "overall_readiness": circuit.get("overall_readiness"),
                "board_count": circuit.get("board_count"),
            },
            commit=True,
        )
        if "error" in saved:
            raise HTTPException(status_code=404, detail=saved["error"])

    return {
        "status": "success",
        "circuit": circuit,
        "saved": saved,
        "metadata": {"user_id": current_user.get("user_id"), "committed": bool(commit_analysis)},
    }


@app.post("/circuit/reasoning/assess")
def circuit_reasoning_assess(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: BoardSessionStore = Depends(get_board_session_store),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
) -> Dict[str, Any]:
    body, source_session_id, added_circuit_context = _salvage_payload_with_session_context(payload, store)
    include_salvage_plan = bool(body.get("include_salvage_plan", True))
    salvage_plan = body.get("salvage_plan") if isinstance(body.get("salvage_plan"), dict) else None
    if include_salvage_plan and salvage_plan is None:
        plan_payload = dict(body)
        plan_payload["use_llm_reasoner"] = False
        salvage_plan = planner.plan(plan_payload)
        body["salvage_plan"] = salvage_plan
        body["functional_reuse_plan"] = salvage_plan.get("functional_reuse_plan")

    reasoner = CircuitAIReasoner(
        enable_llm=bool(body.get("use_llm_reasoner") or body.get("use_llm")),
    )
    reasoning = reasoner.assess(body)
    return {
        "status": "success",
        "reasoning": reasoning,
        "salvage_plan": salvage_plan if include_salvage_plan else None,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "source_session_id": source_session_id,
            "added_circuit_context": added_circuit_context,
            "llm_requested": bool(body.get("use_llm_reasoner") or body.get("use_llm")),
        },
    }


@app.get("/circuit/reasoning/model-status")
def circuit_reasoning_model_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "status": "success",
        "model_runtime": circuit_ai_model_status(),
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


@app.post("/salvage/functional-workflow/golden")
def salvage_functional_workflow_golden(
    payload: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    body = payload or {}
    runner = FunctionalSalvageWorkflowRunner(store=store, planner=planner)
    report = runner.run(commit_sessions=bool(body.get("commit_sessions", False)))
    return {
        "status": "success" if report.get("overall_status") == "pass" else "needs_review",
        "workflow": report,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "commit_sessions": bool(body.get("commit_sessions", False)),
        },
    }


@app.post("/resource/strategy")
def resource_strategy(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    strategy = build_resource_strategy(payload)
    return {
        "resource_strategy": strategy,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "strategy_mode": strategy.get("strategy_mode"),
            "build_readiness": (strategy.get("build_readiness") or {}).get("status"),
        },
    }


@app.post("/hardware/diy-project/plan")
def diy_project_plan(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    body = payload or {}
    plan = build_diy_project_engineering_plan(body)
    test_kit = build_design_test_kit({**body, "diy_project_engineering": plan})
    suite = test_kit.get("test_suite") if isinstance(test_kit.get("test_suite"), dict) else {}
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    return {
        "diy_project_engineering": plan,
        "design_test_kit": test_kit,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "available": bool(plan.get("available")),
            "profile_id": ((plan.get("project_intent") or {}).get("profile_id") if isinstance(plan.get("project_intent"), dict) else None),
            "readiness": ((plan.get("readiness") or {}).get("level") if isinstance(plan.get("readiness"), dict) else None),
            "test_kit_score": suite.get("score"),
            "test_kit_decision": release.get("decision"),
        },
    }


@app.post("/hardware/test-kit/run")
def hardware_test_kit_run(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    test_kit = build_design_test_kit(payload or {})
    suite = test_kit.get("test_suite") if isinstance(test_kit.get("test_suite"), dict) else {}
    release = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}
    return {
        "design_test_kit": test_kit,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "available": bool(test_kit.get("available")),
            "score": suite.get("score"),
            "decision": release.get("decision"),
            "simulation_available": bool((test_kit.get("simulation") or {}).get("available")) if isinstance(test_kit.get("simulation"), dict) else False,
        },
    }


@app.post("/hardware/field-agent/next-action")
def hardware_field_agent_next_action(
    payload: Dict[str, Any],
    include_model_advisory: bool = False,
    live_model_advisory: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    field_action = build_field_operator_next_action(payload or {})
    call = field_action.get("operational_call") if isinstance(field_action.get("operational_call"), dict) else {}
    advisory = None
    if include_model_advisory or live_model_advisory:
        advisory = build_field_model_advisory(
            {**(payload or {}), "field_operator": field_action},
            live=bool(live_model_advisory),
        )
    return {
        "field_operator": field_action,
        "field_model_advisory": advisory,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "available": bool(field_action.get("available")),
            "next_action_id": call.get("action_id"),
            "action_type": call.get("action_type"),
            "authority": call.get("authority"),
            "model_advisory_included": advisory is not None,
            "live_model_advisory": bool(live_model_advisory),
        },
    }


@app.post("/hardware/authority-ledger/evaluate")
def hardware_authority_ledger_evaluate(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    ledger = build_authority_ledger(payload or {})
    return {
        "authority_ledger": ledger,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "available": bool(ledger.get("available")),
            "current_authority_level": ledger.get("current_authority_level"),
            "authority_score": ledger.get("authority_score"),
            "claim_production_repair_release": ((ledger.get("can") or {}).get("claim_production_repair_release")),
        },
    }


@app.post("/hardware/production-casefile/run")
def hardware_production_casefile_run(
    payload: Dict[str, Any],
    live_model_advisory: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    casefile = build_production_casefile(payload or {}, live_model_advisory=bool(live_model_advisory))
    return {
        "production_casefile": casefile,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "casefile_id": casefile.get("casefile_id"),
            "current_authority_level": (casefile.get("summary") or {}).get("current_authority_level"),
            "authority_score": (casefile.get("summary") or {}).get("authority_score"),
            "production_authorized": (casefile.get("summary") or {}).get("production_authorized"),
            "live_model_advisory": bool(live_model_advisory),
        },
    }


@app.post("/hardware/omniscience-map/run")
def hardware_omniscience_map_run(
    payload: Dict[str, Any],
    include_evidence_graph: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    omniscience = build_board_omniscience_map(payload or {}, include_evidence_graph=bool(include_evidence_graph))
    summary = omniscience.get("summary") if isinstance(omniscience.get("summary"), dict) else {}
    return {
        "board_omniscience_map": omniscience,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "omniscience_level": summary.get("omniscience_level"),
            "omniscience_score": summary.get("omniscience_score"),
            "authority_level": summary.get("authority_level"),
            "production_authorized": summary.get("production_authorized"),
            "next_best_action_id": summary.get("next_best_action_id"),
            "include_evidence_graph": bool(include_evidence_graph),
        },
    }


@app.post("/hardware/diy-project/session")
def diy_project_session_update(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    store: DIYProjectSessionStore = Depends(get_diy_project_session_store),
) -> Dict[str, Any]:
    result = store.update_from_turn(payload or {}, user_id=str(current_user.get("user_id") or "anonymous"))
    plan = result.get("diy_project_engineering") if isinstance(result.get("diy_project_engineering"), dict) else {}
    session = result.get("diy_project_session") if isinstance(result.get("diy_project_session"), dict) else {}
    return {
        **result,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "session_id": session.get("session_id"),
            "turn_count": ((session.get("conversation") or {}).get("turn_count") if isinstance(session.get("conversation"), dict) else None),
            "available": bool(plan.get("available")),
            "profile_id": ((plan.get("project_intent") or {}).get("profile_id") if isinstance(plan.get("project_intent"), dict) else None),
            "readiness": ((plan.get("readiness") or {}).get("level") if isinstance(plan.get("readiness"), dict) else None),
        },
    }


@app.post("/hardware/plan")
def hardware_plan(
    payload: Dict[str, Any],
    commit_session: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    body = dict(payload or {})
    source_session_id = str(
        body.get("session_id")
        or body.get("source_session_id")
        or body.get("board_session_id")
        or ""
    ).strip()
    session = None
    if source_session_id:
        session = store.get_session(source_session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Board session not found: {source_session_id}")

    try:
        plan = HardwarePlanOrchestrator(salvage_planner=planner).plan(body, session=session)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    test_kit_payload = dict(body)
    analysis = plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {}
    diy_plan = analysis.get("diy_project_engineering") if isinstance(analysis.get("diy_project_engineering"), dict) else None
    if diy_plan:
        test_kit_payload["diy_project_engineering"] = diy_plan
    test_kit = build_design_test_kit(test_kit_payload)
    test_suite = test_kit.get("test_suite") if isinstance(test_kit.get("test_suite"), dict) else {}
    release_gate = test_kit.get("release_gate") if isinstance(test_kit.get("release_gate"), dict) else {}

    saved = None
    created_session = None
    if commit_session and source_session_id:
        saved = store.append_analysis(
            source_session_id,
            plan.get("analysis") if isinstance(plan.get("analysis"), dict) else {},
            source="hardware_plan",
            summary={
                "status": (plan.get("integrated_plan") or {}).get("status"),
                "recommended_path": (plan.get("integrated_plan") or {}).get("recommended_path"),
                "selected_resource_count": (plan.get("integrated_plan") or {}).get("selected_resource_count"),
            },
            commit=True,
        )
        if "error" in saved:
            raise HTTPException(status_code=404, detail=saved["error"])
    elif commit_session:
        created_session = store.create_session(
            plan.get("session_payload") if isinstance(plan.get("session_payload"), dict) else {},
            user_id=str(current_user.get("user_id") or "anonymous"),
            commit=True,
        )

    return {
        "hardware_plan": plan,
        "design_test_kit": test_kit,
        "session": created_session,
        "saved": saved,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "source_session_id": source_session_id or None,
            "committed": bool(saved or created_session),
            "status": (plan.get("integrated_plan") or {}).get("status"),
            "strategy_mode": plan.get("strategy_mode"),
            "test_kit_score": test_suite.get("score"),
            "test_kit_decision": release_gate.get("decision"),
        },
    }


def _salvage_payload_with_session_context(
    payload: Dict[str, Any],
    store: BoardSessionStore,
) -> tuple[Dict[str, Any], str | None, bool]:
    body = dict(payload or {})
    session_id = str(
        body.get("session_id")
        or body.get("source_session_id")
        or body.get("board_session_id")
        or ""
    ).strip()
    if not session_id:
        return body, None, False

    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Board session not found: {session_id}")

    added_circuit_context = False
    if not isinstance(body.get("analysis"), dict) and not isinstance(body.get("circuit"), dict):
        try:
            body["analysis"] = analyze_circuit_session(
                session,
                design_payload=body.get("design") if isinstance(body.get("design"), dict) else None,
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        added_circuit_context = True
    body["source_session_id"] = session_id
    return body, session_id, added_circuit_context


def _link_salvage_session_payload(session_payload: Dict[str, Any], source_session_id: str | None) -> Dict[str, Any]:
    if not source_session_id:
        return session_payload
    linked = dict(session_payload)
    linked["source_session_id"] = source_session_id
    case_file = dict(linked.get("case_file") or {})
    case_file["source_session_id"] = source_session_id
    linked["case_file"] = case_file
    return linked


@app.post("/salvage/splice-plan")
def salvage_splice_plan(
    payload: Dict[str, Any],
    commit_session: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    payload, source_session_id, added_circuit_context = _salvage_payload_with_session_context(payload, store)
    plan = planner.plan(payload)
    session = None
    if commit_session:
        session_payload = plan.get("session_payload") if isinstance(plan.get("session_payload"), dict) else {}
        session_payload = _link_salvage_session_payload(session_payload, source_session_id)
        session = store.create_session(
            session_payload,
            user_id=str(current_user.get("user_id") or "anonymous"),
            commit=True,
        )
    return {
        "splice_plan": plan,
        "session": session,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "committed_session": bool(session),
            "source_session_id": source_session_id,
            "added_circuit_context": added_circuit_context,
        },
    }


@app.post("/salvage/splice-case")
def salvage_splice_case(
    payload: Dict[str, Any],
    commit: bool = True,
    current_user: Dict[str, Any] = Depends(get_current_user),
    planner: SalvageSplicePlanner = Depends(get_salvage_splice_planner),
    store: BoardSessionStore = Depends(get_board_session_store),
) -> Dict[str, Any]:
    payload, source_session_id, added_circuit_context = _salvage_payload_with_session_context(payload, store)
    plan = planner.plan(payload)
    session_payload = plan.get("session_payload") if isinstance(plan.get("session_payload"), dict) else {}
    session_payload = _link_salvage_session_payload(session_payload, source_session_id)
    session = store.create_session(
        session_payload,
        user_id=str(current_user.get("user_id") or "anonymous"),
        commit=commit,
    )
    return {
        "splice_plan": plan,
        "session": session,
        "metadata": {
            "user_id": current_user.get("user_id"),
            "committed": commit,
            "source_session_id": source_session_id,
            "added_circuit_context": added_circuit_context,
        },
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
