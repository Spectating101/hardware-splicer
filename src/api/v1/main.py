from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import time
import numpy as np
from PIL import Image, ImageOps
import io
from typing import Dict, Any, List, Optional
from loguru import logger
import uuid
from datetime import datetime, timezone

from ...core.ingest import CircuitAnalyzer
from ...core.database import CircuitDatabase
from ...config import settings
from ...vision.loader import get_detector, preprocess_image, postprocess_detections
from .auth import verify_api_key, get_current_user
from .models import (
    AnalysisRequest, AnalysisResponse, ComponentInfo, ProjectTemplate,
    ErrorResponse, SuccessResponse, BatchAnalysisRequest, BatchAnalysisResponse,
    Component, AnalysisMetadata
)
from .rate_limiting import rate_limit
from .metrics import REQUEST_COUNT, ANALYZE_LATENCY, BATCH_ANALYZE_LATENCY
from .billing import router as billing_router
from ...services.usage_tracker import usage_tracker

# Initialize FastAPI app with proper API versioning
app = FastAPI(
    title="Circuit.AI API",
    description="Enterprise-grade PCB analysis API platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Security scheme
security = HTTPBearer()

# Upload validation settings
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSION = 8000           # 8K max dimension to prevent memory exhaustion
MOBILE_OPTIMIZED_DIMENSION = 4096    # Downscale large handheld captures for stability

# Basic image validation helper to avoid oversized or malformed uploads
def _validate_image_upload(contents: bytes, filename: Optional[str] = None) -> Image.Image:
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size must be less than 10MB"
        )
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()  # validate header without fully decoding
        # Re-open to a clean handle, fix orientation, and normalize mode
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(contents)))
        image = image.convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file"
        )
    
    width, height = image.size
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image dimensions exceed {MAX_IMAGE_DIMENSION}px"
        )

    # Downscale oversized handheld captures to keep memory and latency stable
    max_dim = max(width, height)
    if max_dim > MOBILE_OPTIMIZED_DIMENSION:
        scale = MOBILE_OPTIMIZED_DIMENSION / float(max_dim)
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)

    return image

# Add CORS middleware
# Configure allowed origins from environment or use safe defaults
allowed_origins = settings.cors_origins if hasattr(settings, 'cors_origins') else [
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

# Initialize components
analyzer = CircuitAnalyzer()
database = CircuitDatabase()

# Include billing routes
app.include_router(billing_router)

# Global model cache
_yolo_model = None
_enhanced_detector_singleton: Optional[Any] = None


def get_enhanced_detector():
    """Lazy-load and cache the enhanced detector to avoid reloading models per request."""
    global _enhanced_detector_singleton
    if _enhanced_detector_singleton is None:
        from ...vision.enhanced_detector import EnhancedComponentDetector
        _enhanced_detector_singleton = EnhancedComponentDetector()
    return _enhanced_detector_singleton

# Health check endpoint
@app.get("/health", response_model=SuccessResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return SuccessResponse(
        success=True,
        data={
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "detector": "operational",
                "mapper": "operational", 
                "analyzer": "operational",
                "database": "operational"
            }
        }
    )

# Main analysis endpoint
@app.post("/analyze", response_model=AnalysisResponse)
@rate_limit(requests_per_minute=60)
async def analyze_pcb(
    request: Request,
    file: UploadFile = File(..., description="PCB image file (PNG, JPG, JPEG)"),
    backend: Optional[str] = Form(None, description="Detection backend (yolo, enhanced)"),
    enable_ocr: bool = Form(False, description="Enable OCR text extraction"),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze a PCB image for component detection and value assessment.
    
    This endpoint processes uploaded PCB images and returns detailed analysis
    including component detection, value assessment, and educational insights.
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image (PNG, JPG, JPEG)"
            )
        
        # Read and process image with safety checks
        contents = await file.read()
        image = _validate_image_upload(contents, file.filename)
        image_np = np.array(image)
        file_size = len(contents)
        
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Analyze PCB
        REQUEST_COUNT.labels(endpoint="analyze", user_id=current_user.get("user_id", "anonymous")).inc()
        start_ts = time.perf_counter()
        
        results = analyzer.analyze_pcb(
            image_np, 
            backend=backend or "enhanced", 
            enable_ocr=enable_ocr
        )
        
        # Generate summary
        summary = analyzer.get_analysis_summary(results)
        elapsed = time.perf_counter() - start_ts
        ANALYZE_LATENCY.observe(elapsed)
        
        # Store results
        results["analysis_metadata"] = {
            "analysis_id": analysis_id,
            "user_id": current_user.get("user_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_time": round(elapsed, 4),
            "file_name": file.filename,
            "file_size": file_size,
            "backend_used": backend or "enhanced",
            "ocr_enabled": enable_ocr
        }
        
        # Track usage
        usage_tracker.track_request(
            user_id=current_user.get("user_id"),
            endpoint="analyze",
            success=True,
            analysis_time=elapsed,
            components_detected=len(results.get("detections", []))
        )
        
        # Store in database
        db_analysis_id = database.store_analysis_result(results, file.filename)
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            components=results.get("detections", []),
            total_value=summary.get("total_value", 0.0),
            analysis_time=elapsed,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=results["analysis_metadata"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in PCB analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

# Batch analysis endpoint
@app.post("/analyze/batch", response_model=BatchAnalysisResponse)
@rate_limit(requests_per_minute=10)
async def analyze_batch(
    request: BatchAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Batch analyze multiple PCB images.
    
    Process multiple images in a single request for efficient bulk analysis.
    """
    try:
        if len(request.images) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 images per batch request"
            )
        
        REQUEST_COUNT.labels(endpoint="analyze_batch", user_id=current_user.get("user_id", "anonymous")).inc()
        batch_start = time.perf_counter()
        
        results = []
        for item in request.images:
            try:
                # Decode base64 image
                import base64
                image_bytes = base64.b64decode(item.content_base64)
                image = _validate_image_upload(image_bytes, item.filename)
                image_np = np.array(image)
                
                # Analyze
                start_ts = time.perf_counter()
                analysis_results = analyzer.analyze_pcb(
                    image_np, 
                    backend=item.backend or "enhanced", 
                    enable_ocr=item.enable_ocr or False
                )
                summary = analyzer.get_analysis_summary(analysis_results)
                elapsed = time.perf_counter() - start_ts
                
                # Generate analysis ID
                analysis_id = str(uuid.uuid4())
                
                results.append({
                    "success": True,
                    "analysis_id": analysis_id,
                    "filename": item.filename,
                    "components": analysis_results.get("detections", []),
                    "total_value": summary.get("total_value", 0.0),
                    "analysis_time": elapsed,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            except Exception as inner:
                results.append({
                    "success": False,
                    "filename": item.filename,
                    "error": str(inner),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        BATCH_ANALYZE_LATENCY.observe(time.perf_counter() - batch_start)
        
        return BatchAnalysisResponse(
            success=True,
            results=results,
            total_processed=len(results),
            batch_time=time.perf_counter() - batch_start,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analyze failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch analyze failed"
        )

# Component information endpoint
@app.get("/components", response_model=SuccessResponse)
async def get_components(
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    Get information about supported electronic components.
    
    Retrieve detailed information about component types, capabilities,
    and specifications available in the Circuit.AI database.
    """
    try:
        components = database.get_component_info(search, category, limit, offset)
        
        return SuccessResponse(
            success=True,
            data={
                "components": components,
                "total": len(components),
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting components: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve components"
        )

# Project templates endpoint
@app.get("/projects", response_model=SuccessResponse)
async def get_projects(
    difficulty: Optional[str] = None,
    components: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """
    Get educational project templates and recommendations.
    
    Retrieve project templates based on difficulty level and available components.
    """
    try:
        projects = database.get_project_templates(difficulty, components, limit, offset)
        
        return SuccessResponse(
            success=True,
            data={
                "projects": projects,
                "total": len(projects),
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting projects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve projects"
        )

# Educational content endpoint
@app.get("/educational/{component_id}", response_model=SuccessResponse)
async def get_educational_content(
    component_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get educational content and tutorials for a specific component.
    
    Retrieve detailed educational materials, tutorials, and learning resources
    for the specified electronic component.
    """
    try:
        content = database.get_educational_content(component_id)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Educational content not found for this component"
            )
        
        return SuccessResponse(
            success=True,
            data=content
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting educational content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve educational content"
        )

# Analysis history endpoint
@app.get("/analyses", response_model=SuccessResponse)
async def get_analysis_history(
    limit: int = 20,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's analysis history.
    
    Retrieve a paginated list of the user's previous PCB analyses.
    """
    try:
        analyses = database.get_user_analyses(
            current_user.get("user_id"),
            limit, offset, date_from, date_to
        )
        
        return SuccessResponse(
            success=True,
            data={
                "analyses": analyses,
                "total": len(analyses),
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting analysis history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis history"
        )

# Get specific analysis
@app.get("/analyses/{analysis_id}", response_model=SuccessResponse)
async def get_analysis(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific analysis by ID.
    
    Retrieve detailed results for a specific PCB analysis.
    """
    try:
        analysis = database.get_analysis_by_id(analysis_id)
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        # Check if user owns this analysis
        if analysis.get("user_id") != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this analysis"
            )
        
        return SuccessResponse(
            success=True,
            data=analysis
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis"
        )

# Export analysis as CSV
@app.get("/analyses/{analysis_id}/export.csv")
async def export_analysis_csv(
    analysis_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Export analysis results as CSV.
    
    Download analysis results in CSV format for further processing.
    """
    try:
        analysis = database.get_analysis_by_id(analysis_id)
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis not found"
            )
        
        # Check ownership
        if analysis.get("user_id") != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this analysis"
            )
        
        # Generate CSV
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write analysis data
        writer.writerow(["Analysis ID", analysis_id])
        writer.writerow(["Timestamp", analysis.get("timestamp")])
        writer.writerow(["Total Components", len(analysis.get("components", []))])
        writer.writerow([])
        
        # Write components
        writer.writerow(["Components"])
        writer.writerow(["Type", "Confidence", "Value", "Position"])
        for component in analysis.get("components", []):
            writer.writerow([
                component.get("type", ""),
                component.get("confidence", 0),
                component.get("value", 0),
                f"({component.get('x', 0)}, {component.get('y', 0)})"
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export CSV"
        )

# API usage statistics
@app.get("/usage", response_model=SuccessResponse)
async def get_usage_stats(
    period: str = "day",
    current_user: dict = Depends(get_current_user)
):
    """
    Get API usage statistics for the current user.
    
    Retrieve usage metrics including request counts, rate limits, and quotas.
    """
    try:
        user_id = current_user.get("user_id")
        
        # Get usage statistics
        usage_stats = usage_tracker.get_usage_stats(user_id, period)
        
        # Get quota status
        quota_status = usage_tracker.check_quotas(user_id)
        
        # Get user plan
        user_plan = usage_tracker.get_user_plan(user_id)
        plan_limits = usage_tracker.get_plan_limits(user_plan)
        
        return SuccessResponse(
            success=True,
            data={
                "usage": usage_stats,
                "quotas": quota_status,
                "plan": user_plan,
                "limits": plan_limits
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage statistics"
        )

# YOLO-based PCB analysis endpoint
@app.post("/analyze-yolo", response_model=AnalysisResponse)
@rate_limit(requests_per_minute=30, requests_per_hour=500)
async def analyze_pcb_yolo(
    file: UploadFile = File(...),
    model_name: str = "electrocom61_v1",
    confidence: float = 0.25,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze PCB image using YOLO model for component detection.
    
    This endpoint uses a trained YOLO model for fast, accurate component detection.
    """
    try:
        # Validate file
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Read image data
        image_data = await file.read()
        _validate_image_upload(image_data, file.filename)
        
        # Preprocess image
        img = preprocess_image(image_data)
        if img is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process image"
            )
        
        # Get YOLO model
        model = get_detector(model_name)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Model {model_name} not available"
            )
        
        # Run inference
        start_time = time.perf_counter()
        results = model(img)
        inference_time = time.perf_counter() - start_time
        
        # Postprocess results
        detections = postprocess_detections(results, confidence)
        
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        
        # Create response
        components = []
        for detection in detections:
            component = ComponentInfo(
                name=detection["class_name"],
                category=detection["class_name"],
                confidence=detection["confidence"],
                bbox=detection["bbox"],
                value=None,  # Will be enriched later
                package=None,
                description=f"Detected {detection['class_name']} component"
            )
            components.append(component)
        
        # Track usage
        usage_tracker.track_request(
            user_id=current_user.get("user_id"),
            endpoint="analyze-yolo",
            success=True,
            analysis_time=inference_time,
            components_detected=len(components)
        )
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            components=components,
            summary={
                "total_components": len(components),
                "model_version": model_name,
                "inference_time": round(inference_time, 4),
                "confidence_threshold": confidence,
                "image_size": f"{img.shape[1]}x{img.shape[0]}"
            },
            processing_time=round(inference_time, 4)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YOLO analysis error: {e}")
        
        # Track failed request
        usage_tracker.track_request(
            user_id=current_user.get("user_id"),
            endpoint="analyze-yolo",
            success=False,
            analysis_time=0.0,
            components_detected=0
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed"
        )


@app.post("/detect-components", response_model=AnalysisResponse)
@rate_limit(requests_per_minute=30, requests_per_hour=500)
async def detect_pcb_components(
    file: UploadFile = File(...),
    confidence: float = 0.5,
    current_user: dict = Depends(get_current_user)
):
    """
    Detect PCB components using Circuit-AI trained YOLOv8 model.
    
    This endpoint uses the trained real_pcb_v1 model which detects:
    - Cap1, Cap2, Cap3, Cap4 (Capacitors)
    - MOSFET (Transistor)
    - Mov (Metal Oxide Varistor)
    - Resistor, Resestor
    - Transformer
    """
    try:
        # Validate file
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Read image as PIL Image for enhanced detector
        image_data = await file.read()
        img_pil = _validate_image_upload(image_data, file.filename)
        img_array = np.array(img_pil)
        
        # Import enhanced detector which now uses trained model
        from ...vision.enhanced_detector import DetectionMethod
        
        # Reuse cached detector (loads trained model on first use)
        detector = get_enhanced_detector()
        
        # Run detection
        start_time = time.perf_counter()
        detections = detector.detect_components(
            img_array,
            methods=[DetectionMethod.YOLO],
            enable_ocr=False,
            enable_quality_assessment=True
        )
        inference_time = time.perf_counter() - start_time
        
        # Filter by confidence
        detections = [d for d in detections if d.confidence >= confidence]
        
        # Generate analysis ID
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Component class mappings for better descriptions
        component_mappings = {
            "Cap1": {"name": "Capacitor Type 1", "function": "Energy storage in electronic circuits", "value": 0.10},
            "Cap2": {"name": "Capacitor Type 2", "function": "Energy storage in electronic circuits", "value": 0.15},
            "Cap3": {"name": "Capacitor Type 3", "function": "Energy storage in electronic circuits", "value": 0.20},
            "Cap4": {"name": "Capacitor Type 4", "function": "Energy storage in electronic circuits", "value": 0.25},
            "MOSFET": {"name": "MOSFET Transistor", "function": "Switching and amplification in power electronics", "value": 0.50},
            "Mov": {"name": "Metal Oxide Varistor", "function": "Surge protection and voltage regulation", "value": 0.30},
            "Resistor": {"name": "Resistor", "function": "Current limiting and voltage division", "value": 0.05},
            "Resestor": {"name": "Resistor (Variant)", "function": "Current limiting and voltage division", "value": 0.05},
            "Transformer": {"name": "Transformer", "function": "Voltage and impedance transformation", "value": 1.50},
        }
        
        # Create response components
        components = []
        total_value = 0.0
        
        for detection in detections:
            class_name = detection.class_name
            mapping = component_mappings.get(class_name, {"name": class_name, "function": "Unknown component", "value": 0.10})
            
            # Calculate center coordinates
            bbox = detection.bbox  # [x1, y1, x2, y2]
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            component = Component(
                type=class_name,
                name=mapping["name"],
                confidence=float(detection.confidence),
                bbox=list(bbox),
                center={"x": center_x, "y": center_y},
                value=mapping["value"],
                function=mapping["function"],
                specifications={
                    "detection_method": "YOLOv8m",
                    "model": "real_pcb_v1",
                    "class": class_name
                },
                educational_value="High",
                reuse_value="High"
            )
            components.append(component)
            total_value += mapping["value"]
        
        # Track usage
        usage_tracker.track_request(
            user_id=current_user.get("user_id"),
            endpoint="detect-components",
            success=True,
            analysis_time=inference_time,
            components_detected=len(components)
        )
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            components=components,
            total_value=total_value,
            analysis_time=inference_time,
            timestamp=timestamp,
            metadata=AnalysisMetadata(
                analysis_id=analysis_id,
                user_id=current_user.get("user_id"),
                timestamp=timestamp,
                processing_time=inference_time,
                file_name=file.filename,
                file_size=len(image_data),
                backend_used="Circuit-AI YOLOv8m real_pcb_v1",
                ocr_enabled=False
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Component detection error: {e}", exc_info=True)
        
        usage_tracker.track_request(
            user_id=current_user.get("user_id"),
            endpoint="detect-components",
            success=False,
            analysis_time=0.0,
            components_detected=0
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
