from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class ComponentType(str, Enum):
    IC_CHIP = "ic_chip"
    CAPACITOR = "capacitor"
    RESISTOR = "resistor"
    CONNECTOR = "connector"
    TRANSFORMER = "transformer"
    DIODE = "diode"
    LED = "led"
    TRANSISTOR = "transistor"
    INDUCTOR = "inductor"
    CRYSTAL = "crystal"

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class BackendType(str, Enum):
    YOLO = "yolo"
    ENHANCED = "enhanced"

# Request Models
class AnalysisRequest(BaseModel):
    """Request model for single PCB analysis."""
    backend: Optional[BackendType] = Field(None, description="Detection backend to use")
    enable_ocr: bool = Field(False, description="Enable OCR text extraction")
    return_annotated_image: bool = Field(False, description="Return annotated image in response")

class BatchImageItem(BaseModel):
    """Individual image item for batch analysis."""
    filename: str = Field(..., description="Original filename")
    content_base64: str = Field(..., description="Base64 encoded image content")
    backend: Optional[BackendType] = Field(None, description="Detection backend to use")
    enable_ocr: bool = Field(False, description="Enable OCR text extraction")

class BatchAnalysisRequest(BaseModel):
    """Request model for batch PCB analysis."""
    images: List[BatchImageItem] = Field(..., description="List of images to analyze", max_items=10)

# Response Models
class Component(BaseModel):
    """Detected component information."""
    type: str = Field(..., description="Component type")
    name: str = Field(..., description="Component name")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence score")
    bbox: List[float] = Field(..., description="Bounding box coordinates [x1, y1, x2, y2]")
    center: Dict[str, float] = Field(..., description="Center coordinates")
    value: float = Field(..., description="Estimated market value in USD")
    function: str = Field(..., description="Component function description")
    specifications: Optional[Dict[str, Any]] = Field(None, description="Component specifications")
    educational_value: str = Field(..., description="Educational value rating")
    reuse_value: str = Field(..., description="Reuse value rating")

class AnalysisMetadata(BaseModel):
    """Analysis metadata information."""
    analysis_id: str = Field(..., description="Unique analysis identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    timestamp: str = Field(..., description="Analysis timestamp (ISO format)")
    processing_time: float = Field(..., description="Processing time in seconds")
    file_name: Optional[str] = Field(None, description="Original filename")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    backend_used: str = Field(..., description="Backend used for analysis")
    ocr_enabled: bool = Field(..., description="Whether OCR was enabled")
    detection_quality: Optional[str] = Field(None, description="Detection quality band (none/low/medium/high)")
    detection_count: Optional[int] = Field(None, description="Number of detections")
    detection_avg_confidence: Optional[float] = Field(None, description="Average detection confidence")
    model_source: Optional[str] = Field(None, description="Detector model source (trained/fallback)")
    fallback_used: Optional[bool] = Field(None, description="Whether a fallback model was used")

class AnalysisResponse(BaseModel):
    """Response model for PCB analysis."""
    success: bool = Field(..., description="Whether the analysis was successful")
    analysis_id: str = Field(..., description="Unique analysis identifier")
    components: List[Component] = Field(..., description="Detected components")
    total_value: float = Field(..., description="Total estimated value of all components")
    analysis_time: float = Field(..., description="Analysis processing time in seconds")
    timestamp: str = Field(..., description="Response timestamp (ISO format)")
    metadata: AnalysisMetadata = Field(..., description="Analysis metadata")

class BatchAnalysisItem(BaseModel):
    """Individual analysis result in batch response."""
    success: bool = Field(..., description="Whether this analysis was successful")
    analysis_id: Optional[str] = Field(None, description="Unique analysis identifier")
    filename: str = Field(..., description="Original filename")
    components: Optional[List[Component]] = Field(None, description="Detected components")
    total_value: Optional[float] = Field(None, description="Total estimated value")
    analysis_time: Optional[float] = Field(None, description="Analysis processing time")
    timestamp: str = Field(..., description="Response timestamp")
    error: Optional[str] = Field(None, description="Error message if analysis failed")

class BatchAnalysisResponse(BaseModel):
    """Response model for batch PCB analysis."""
    success: bool = Field(..., description="Whether the batch analysis was successful")
    results: List[BatchAnalysisItem] = Field(..., description="Individual analysis results")
    total_processed: int = Field(..., description="Total number of images processed")
    batch_time: float = Field(..., description="Total batch processing time in seconds")
    timestamp: str = Field(..., description="Response timestamp (ISO format)")

class ComponentInfo(BaseModel):
    """Component information for the components endpoint."""
    type: str = Field(..., description="Component type identifier")
    name: str = Field(..., description="Human-readable component name")
    description: str = Field(..., description="Component description")
    category: str = Field(..., description="Component category")
    capabilities: List[str] = Field(..., description="List of component capabilities")
    specifications: Dict[str, Any] = Field(..., description="Technical specifications")
    market_value_range: Dict[str, float] = Field(..., description="Market value range (min, max)")
    educational_value: str = Field(..., description="Educational value rating")
    reuse_value: str = Field(..., description="Reuse value rating")
    common_applications: List[str] = Field(..., description="Common applications")

class ProjectTemplate(BaseModel):
    """Project template information."""
    id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    difficulty: DifficultyLevel = Field(..., description="Project difficulty level")
    time_estimate: str = Field(..., description="Estimated completion time")
    components_needed: List[str] = Field(..., description="Required components")
    components_optional: List[str] = Field(..., description="Optional components")
    tools_needed: List[str] = Field(..., description="Required tools")
    skills_learned: List[str] = Field(..., description="Skills developed in this project")
    educational_value: str = Field(..., description="Educational value rating")
    estimated_cost: float = Field(..., description="Estimated project cost in USD")
    safety_level: str = Field(..., description="Safety level rating")
    prerequisites: List[str] = Field(..., description="Prerequisite knowledge/skills")
    resources: Dict[str, str] = Field(..., description="Additional resources and links")

class EducationalContent(BaseModel):
    """Educational content for components."""
    component_id: str = Field(..., description="Component identifier")
    title: str = Field(..., description="Content title")
    description: str = Field(..., description="Content description")
    content_type: str = Field(..., description="Type of content (tutorial, guide, video, etc.)")
    difficulty: DifficultyLevel = Field(..., description="Content difficulty level")
    duration: Optional[str] = Field(None, description="Estimated learning duration")
    topics_covered: List[str] = Field(..., description="Topics covered in this content")
    resources: List[Dict[str, str]] = Field(..., description="Learning resources and links")
    prerequisites: List[str] = Field(..., description="Prerequisite knowledge")
    learning_objectives: List[str] = Field(..., description="Learning objectives")

class UsageStats(BaseModel):
    """API usage statistics."""
    user_id: str = Field(..., description="User identifier")
    period: str = Field(..., description="Statistics period")
    total_requests: int = Field(..., description="Total API requests made")
    successful_requests: int = Field(..., description="Successful requests")
    failed_requests: int = Field(..., description="Failed requests")
    total_analysis_time: float = Field(..., description="Total analysis time in seconds")
    average_analysis_time: float = Field(..., description="Average analysis time")
    components_detected: int = Field(..., description="Total components detected")
    images_processed: int = Field(..., description="Total images processed")
    quota_used: int = Field(..., description="Quota used this period")
    quota_remaining: int = Field(..., description="Quota remaining this period")
    rate_limit_remaining: int = Field(..., description="Rate limit remaining")

# Generic Response Models
class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = Field(True, description="Whether the request was successful")
    data: Union[Dict[str, Any], List[Any]] = Field(..., description="Response data")
    message: Optional[str] = Field(None, description="Optional success message")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Response timestamp")

class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = Field(False, description="Whether the request was successful")
    error: Dict[str, Any] = Field(..., description="Error information")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Error timestamp")

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[str] = Field(None, description="Additional error details")
    field: Optional[str] = Field(None, description="Field that caused the error (for validation errors)")

# API Key Models
class APIKeyInfo(BaseModel):
    """API key information."""
    key_id: str = Field(..., description="API key identifier")
    name: str = Field(..., description="API key name")
    created_at: str = Field(..., description="Creation timestamp")
    last_used: Optional[str] = Field(None, description="Last usage timestamp")
    usage_count: int = Field(..., description="Total usage count")
    is_active: bool = Field(..., description="Whether the key is active")
    permissions: List[str] = Field(..., description="Key permissions")

class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., description="API key name", min_length=1, max_length=100)
    permissions: List[str] = Field(default_factory=list, description="Key permissions")

class CreateAPIKeyResponse(BaseModel):
    """Response for API key creation."""
    success: bool = Field(True, description="Whether the key was created successfully")
    api_key: str = Field(..., description="The generated API key (only shown once)")
    key_info: APIKeyInfo = Field(..., description="API key information")
    message: str = Field(..., description="Success message")
