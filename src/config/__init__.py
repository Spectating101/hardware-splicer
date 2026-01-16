from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings using Pydantic."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    cerebras_api_key: Optional[str] = None
    
    # Database
    database_url: str = "sqlite:///./data/circuit_ai.db"
    
    # Model Paths
    yolo_model_path: str = "models/yolo/pcb_detector.pt"
    
    # Detection pipeline
    # Options: "demo" (enhanced demo), "classical" (OpenCV), "yolo" (model), "remote" (HTTP)
    detection_backend: str = "yolo"
    enable_ocr: bool = True
    ocr_lang: str = "eng"

    # LLM provider configuration (defaults prefer non-OpenAI)
    llm_provider: str = "cohere"  # options: "cohere", "mistral", "cerebras", "openai"
    llm_model: str = "command-r"   # e.g., Cohere "command-r", Mistral "mistral-large-latest", Cerebras model name
    llm_api_base: Optional[str] = None  # optional override for custom endpoints (e.g., Cerebras)

    # LLM toggles
    llm_enabled: bool = True
    llm_cache_enabled: bool = True
    llm_cache_path: str = "data/cache/llm_cache.json"

    # Remote detection (optional)
    remote_detect_url: Optional[str] = None

    # Auth
    api_key: Optional[str] = None
    jwt_secret: Optional[str] = None

    # Storage
    upload_dir: str = "data/uploads"
    annotated_dir: str = "data/annotated"

    # Classical CV confidence weights
    cv_aspect_weight: float = 0.35
    cv_edge_density_weight: float = 0.35
    cv_rectangularity_weight: float = 0.2
    cv_area_norm_weight: float = 0.1
    
    # Logging
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Development
    debug: bool = True
    
    class Config:
        # Prioritize .env.local over .env
        # If .env.local exists, use it; otherwise fall back to .env
        env_file = ".env.local" if Path(".env.local").exists() else ".env"
        case_sensitive = False
        extra = "ignore"  # Allow and ignore extra environment variables


# Global settings instance
settings = Settings()

# Debug: Log which API keys are configured
import logging
logger = logging.getLogger(__name__)
if settings.cerebras_api_key:
    logger.debug(f"Cerebras API key configured: {settings.cerebras_api_key[:10]}...")
if settings.openai_api_key:
    logger.debug(f"OpenAI API key configured: {settings.openai_api_key[:10]}...")
if settings.cohere_api_key:
    logger.debug(f"Cohere API key configured: {settings.cohere_api_key[:10]}...")
