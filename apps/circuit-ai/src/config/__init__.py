from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = tuple(
    str(path)
    for path in (
        APP_ROOT / "circuit-ai-frontend" / ".env.local",
        APP_ROOT / ".env",
        APP_ROOT / ".env.local",
    )
    if path.exists()
)


class Settings(BaseSettings):
    """Application settings using Pydantic."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    cerebras_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_base_url: Optional[str] = None
    deepseek_thinking: str = "disabled"
    deepseek_reasoning_effort: Optional[str] = None
    qwen_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    qwen_model: str = "qwen3.5-122b-a10b"
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_vision_model: str = "qwen3-vl-flash"
    qwen_model_rotation: str = "qwen3.5-122b-a10b,qwen3-max,qwen3.5-plus-2026-02-15"
    qwen_vision_model_rotation: str = "qwen3-vl-flash,qwen3-vl-30b-a3b-thinking,qwen-vl-ocr-2025-11-20"
    qwen_low_quota_models: str = "qwen-plus,qwen-plus-2025-07-28"
    qwen_json_mode_disabled: bool = False
    qwen_disabled: bool = False
    qwen_out_of_quota: bool = False
    vision_monthly_usd_limit: float = 0.0
    vision_daily_usd_limit: float = 1.0
    vision_max_usd_per_call: float = 0.05
    copilot_model: str = "gpt-4.1"
    copilot_node_runner: str = "npx -y node@20"
    copilot_timeout_seconds: float = 90
    
    # Database
    database_url: str = "sqlite:///./data/circuit_ai.db"
    
    # Model Paths
    yolo_model_path: str = "models/yolo/pcb_detector.pt"
    
    # Detection pipeline
    # Options: "hybrid"/"ensemble" (YOLO then classical fallback), "classical" (OpenCV), "yolo" (model), "remote" (HTTP)
    detection_backend: str = "hybrid"
    enable_ocr: bool = True
    ocr_lang: str = "eng"

    # LLM provider configuration (defaults prefer non-OpenAI)
    llm_provider: str = "copilot"  # options: "copilot", "cohere", "mistral", "cerebras", "openai", "deepseek", "qwen"
    llm_model: str = "gpt-4.1"   # e.g., Copilot "gpt-4.1", DeepSeek "deepseek-v4-flash", Qwen "qwen3.5-122b-a10b"
    llm_api_base: Optional[str] = None  # optional override for custom endpoints (e.g., Cerebras/DeepSeek)

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
    yolo_min_confidence: float = 0.2
    yolo_nms_iou: float = 0.45
    
    # Logging
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Development
    debug: bool = True
    
    model_config = SettingsConfigDict(
        # Backend .env.local wins; frontend .env.local is only a dev fallback for shared model keys.
        env_file=ENV_FILES or None,
        case_sensitive=False,
        extra="ignore",
    )


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
if settings.deepseek_api_key:
    logger.debug(f"DeepSeek API key configured: {settings.deepseek_api_key[:10]}...")
if settings.qwen_api_key or settings.dashscope_api_key:
    logger.debug("Qwen/DashScope API key configured")
