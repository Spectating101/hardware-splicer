"""
Circuit.AI Python SDK

Official Python SDK for the Circuit.AI PCB Analysis API platform.
"""

from .client import Client
from .models import (
    Component,
    AnalysisResult,
    ProjectTemplate,
    EducationalContent,
    UsageStats,
    CircuitAIError,
    RateLimitError,
    AuthenticationError,
    APIError
)
from .version import __version__

__all__ = [
    "Client",
    "Component",
    "AnalysisResult", 
    "ProjectTemplate",
    "EducationalContent",
    "UsageStats",
    "CircuitAIError",
    "RateLimitError",
    "AuthenticationError",
    "APIError",
    "__version__"
]

__version__ = "1.0.0"
