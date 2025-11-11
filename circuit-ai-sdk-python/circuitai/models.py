"""
Circuit.AI Python SDK Models

Data models for the Circuit.AI API responses and requests.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class ComponentType(str, Enum):
    """Component type enumeration."""
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
    """Difficulty level enumeration."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


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
    
    @validator('bbox')
    def validate_bbox(cls, v):
        if len(v) != 4:
            raise ValueError('bbox must have exactly 4 coordinates')
        return v


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


class AnalysisResult(BaseModel):
    """Response model for PCB analysis."""
    
    success: bool = Field(..., description="Whether the analysis was successful")
    analysis_id: str = Field(..., description="Unique analysis identifier")
    components: List[Component] = Field(..., description="Detected components")
    total_value: float = Field(..., description="Total estimated value of all components")
    analysis_time: float = Field(..., description="Analysis processing time in seconds")
    timestamp: str = Field(..., description="Response timestamp (ISO format)")
    metadata: Optional[AnalysisMetadata] = Field(None, description="Analysis metadata")
    error: Optional[str] = Field(None, description="Error message if analysis failed")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        """Create AnalysisResult from dictionary."""
        # Handle components
        components = []
        for comp_data in data.get("components", []):
            components.append(Component(**comp_data))
        
        # Handle metadata
        metadata = None
        if "metadata" in data:
            metadata = AnalysisMetadata(**data["metadata"])
        
        return cls(
            success=data.get("success", True),
            analysis_id=data.get("analysis_id", ""),
            components=components,
            total_value=data.get("total_value", 0.0),
            analysis_time=data.get("analysis_time", 0.0),
            timestamp=data.get("timestamp", ""),
            metadata=metadata,
            error=data.get("error")
        )


class ProjectTemplate(BaseModel):
    """Project template information."""
    
    id: str = Field(..., description="Unique project identifier")
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    difficulty: DifficultyLevel = Field(..., description="Project difficulty level")
    time_estimate: str = Field(..., description="Estimated completion time")
    components_needed: List[str] = Field(..., description="Required components")
    components_optional: List[str] = Field(default_factory=list, description="Optional components")
    tools_needed: List[str] = Field(default_factory=list, description="Required tools")
    skills_learned: List[str] = Field(default_factory=list, description="Skills developed in this project")
    educational_value: str = Field(..., description="Educational value rating")
    estimated_cost: float = Field(..., description="Estimated project cost in USD")
    safety_level: str = Field(..., description="Safety level rating")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisite knowledge/skills")
    resources: Dict[str, str] = Field(default_factory=dict, description="Additional resources and links")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectTemplate":
        """Create ProjectTemplate from dictionary."""
        return cls(**data)


class EducationalContent(BaseModel):
    """Educational content for components."""
    
    component_id: str = Field(..., description="Component identifier")
    title: str = Field(..., description="Content title")
    description: str = Field(..., description="Content description")
    content_type: str = Field(..., description="Type of content (tutorial, guide, video, etc.)")
    difficulty: DifficultyLevel = Field(..., description="Content difficulty level")
    duration: Optional[str] = Field(None, description="Estimated learning duration")
    topics_covered: List[str] = Field(default_factory=list, description="Topics covered in this content")
    resources: List[Dict[str, str]] = Field(default_factory=list, description="Learning resources and links")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisite knowledge")
    learning_objectives: List[str] = Field(default_factory=list, description="Learning objectives")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EducationalContent":
        """Create EducationalContent from dictionary."""
        return cls(**data)


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
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageStats":
        """Create UsageStats from dictionary."""
        return cls(**data)


# Error Models
class CircuitAIError(Exception):
    """Base exception for Circuit.AI SDK errors."""
    pass


class AuthenticationError(CircuitAIError):
    """Exception raised for authentication errors."""
    pass


class RateLimitError(CircuitAIError):
    """Exception raised for rate limit errors."""
    pass


class APIError(CircuitAIError):
    """Exception raised for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
