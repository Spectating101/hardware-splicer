from contextlib import asynccontextmanager
from functools import lru_cache
import io
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from PIL import Image
from loguru import logger

from src.api.v1.metrics import (
    get_metrics_response,
    record_analysis_metrics,
    record_error_metrics,
    record_request_metrics,
    set_active_connections,
)
from src.config import settings


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
    from src.intelligence.parser import KiCadParser

    return KiCadParser


@lru_cache(maxsize=1)
def get_circuit_parser_analyzer():
    from src.intelligence.analyzer import CircuitAnalyzer

    return CircuitAnalyzer


@lru_cache(maxsize=1)
def get_bom_generator():
    from src.intelligence.bom import BomGenerator

    return BomGenerator


@lru_cache(maxsize=1)
def get_workflow_engine():
    from src.engines.unified_workflow import UnifiedWorkflowEngine

    return UnifiedWorkflowEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    try:
        yield
    finally:
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

# Initialize FastAPI app
app = FastAPI(
    title="Circuit.AI Enhanced API",
    description="Advanced Component Intelligence Platform with Real-time Analysis",
    version="2.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
allowed_origins = settings.cors_origins if hasattr(settings, "cors_origins") else [
    "http://localhost:3000",      # Local development
    "http://localhost:8000",      # Local backend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)

# Pydantic models
class AnalysisRequest(BaseModel):
    backend: str = "ensemble"
    enable_ocr: bool = True
    enable_quality_assessment: bool = True
    enable_caching: bool = True

class BatchAnalysisRequest(BaseModel):
    image_paths: List[str]
    analysis_options: Dict[str, Any] = {}

class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]


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
        response["manufacturing_ready"] = False if result.status == "validation_partial" else (len(critical) == 0 and len(errors) == 0)
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

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time analysis updates."""
    websocket_manager = get_websocket_manager()
    await websocket_manager.connect(websocket, client_id)
    set_active_connections(len(websocket_manager.active_connections))
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "subscribe_analysis":
                analysis_id = message.get("analysis_id")
                if analysis_id:
                    await websocket_manager.subscribe_to_analysis(client_id, analysis_id)
                    await websocket_manager.send_personal_message({
                        "type": "subscription_confirmed",
                        "analysis_id": analysis_id
                    }, client_id)
            
            elif message.get("type") == "unsubscribe_analysis":
                analysis_id = message.get("analysis_id")
                if analysis_id:
                    await websocket_manager.unsubscribe_from_analysis(client_id, analysis_id)
                    await websocket_manager.send_personal_message({
                        "type": "unsubscription_confirmed",
                        "analysis_id": analysis_id
                    }, client_id)
            
            elif message.get("type") == "ping":
                await websocket_manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, client_id)
    
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
        set_active_connections(len(websocket_manager.active_connections))
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        websocket_manager.disconnect(client_id)
        set_active_connections(len(websocket_manager.active_connections))

@app.get("/")
async def root():
    """Root endpoint with enhanced API information."""
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
            "Batch processing capabilities"
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
            "websocket_stats": "/ws/stats - WebSocket connection statistics"
        }
    }

@app.post("/analyze")
async def analyze_pcb(
    file: UploadFile = File(...),
    backend: str = Form("ensemble"),
    enable_ocr: bool = Form(True),
    enable_quality_assessment: bool = Form(True),
    enable_caching: bool = Form(True)
):
    """Enhanced PCB analysis endpoint with real-time progress."""
    started_at = time.perf_counter()
    try:
        # Validate file
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read and process image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        image_np = np.array(image)
        
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Start analysis
        logger.info(f"Starting enhanced analysis {analysis_id}")

        enhanced_analyzer = get_enhanced_analyzer()
        result = await enhanced_analyzer.analyze_pcb(
            image_np,
            backend=backend,
            enable_ocr=enable_ocr,
            enable_quality_assessment=enable_quality_assessment,
            enable_caching=enable_caching,
            analysis_id=analysis_id
        )
        
        # Add file metadata
        result["file_metadata"] = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(image_data)
        }
        record_analysis_metrics(backend=backend, duration=time.perf_counter() - started_at, success=True)
        
        return result
    except HTTPException as e:
        record_analysis_metrics(backend=backend, duration=time.perf_counter() - started_at, success=False)
        record_error_metrics("HTTPException", "/analyze")
        raise e
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        record_analysis_metrics(backend=backend, duration=time.perf_counter() - started_at, success=False)
        record_error_metrics(type(e).__name__, "/analyze")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/netlist")
async def analyze_netlist(file: UploadFile = File(...)):
    """Analyze KiCad Netlist for Electrical Rule Checks (ERC)."""
    try:
        content = await file.read()
        
        # Create temp file
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
                    "count": len(floating_nets)
                },
                "passed": len(floating_nets) == 0
            }
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        logger.error(f"Netlist analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/bom")
async def generate_bom(file: UploadFile = File(...)):
    """Generate Bill of Materials (BOM) CSV from KiCad Netlist."""
    try:
        content = await file.read()
        
        # Create temp file
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
                headers={"Content-Disposition": f"attachment; filename=bom.csv"}
            )
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        logger.error(f"BOM generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch_analyze")
async def batch_analyze(request: BatchAnalysisRequest):
    """Submit batch analysis job."""
    try:
        job_id = get_enhanced_analyzer().submit_batch_analysis_job(
            request.image_paths,
            **request.analysis_options
        )
        
        return {
            "job_id": job_id,
            "status": "submitted",
            "image_count": len(request.image_paths),
            "submitted_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch analysis submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get batch analysis job status."""
    try:
        status = get_enhanced_analyzer().get_batch_job_status(job_id)
        return status
        
    except Exception as e:
        logger.error(f"Job status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Enhanced system health check."""
    try:
        health = get_enhanced_analyzer().get_system_health()
        return health
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/statistics")
async def get_statistics():
    """Get comprehensive system statistics."""
    try:
        stats = get_enhanced_analyzer().get_analysis_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache performance statistics."""
    try:
        stats = get_cache_service().get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/stats")
async def get_queue_stats():
    """Get job queue statistics."""
    try:
        stats = get_queue_service().get_queue_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Queue stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
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
    """Clear cache entries."""
    try:
        deleted_count = get_cache_service().clear(pattern)
        return {
            "message": "Cache cleared successfully",
            "deleted_entries": deleted_count,
            "pattern": pattern
        }
        
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/components")
async def get_component_database():
    """Get enhanced component database."""
    try:
        enhanced_analyzer = get_enhanced_analyzer()
        # This would return the full component database
        # For now, return a summary
        return {
            "total_components": len(enhanced_analyzer.mapper.component_database),
            "component_types": list(enhanced_analyzer.mapper.component_database.keys()),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Component database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects")
async def get_project_templates():
    """Get enhanced project templates."""
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
                    "score": p.score
                }
                for p in projects
            ]
        }
        
    except Exception as e:
        logger.error(f"Project templates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/educational")
async def get_educational_content():
    """Get educational content."""
    try:
        content = get_enhanced_analyzer().mapper.educational_content
        return {
            "total_content": len(content),
            "content": [
                {
                    "title": c.title,
                    "difficulty": c.difficulty,
                    "component_type": c.component_type,
                    "estimated_time": c.estimated_time
                }
                for c in content.values()
            ]
        }
        
    except Exception as e:
        logger.error(f"Educational content error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/repair")
async def get_repair_guides():
    """Get repair guides."""
    try:
        guides = get_enhanced_analyzer().mapper.repair_guides
        return {
            "total_guides": len(guides),
            "guides": [
                {
                    "component_type": g.component_type,
                    "issue": g.issue,
                    "difficulty": g.difficulty,
                    "success_rate": g.success_rate
                }
                for g in guides.values()
            ]
        }
        
    except Exception as e:
        logger.error(f"Repair guides error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics for monitoring."""
    return get_metrics_response()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# --- RECONCILIATION PATCH (Gemini) ---
# This aligns the Backend with the Frontend's expected routes

@app.post("/validate-kicad")
async def validate_kicad_proxy(
    kicad_file: UploadFile = File(...),
    hints: Optional[str] = Form(None)
):
    """
    Proxy endpoint to match Frontend expectations.
    Redirects to the internal analyzer logic.
    """
    logger.info(f"Received KiCad validation request: {kicad_file.filename}")
    
    # 1. Save temp file
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
