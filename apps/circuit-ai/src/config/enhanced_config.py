from pydantic import BaseSettings, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import os

class EnhancedSettings(BaseSettings):
    """Enhanced configuration settings for Circuit.AI."""
    
    # Application settings
    app_name: str = "Circuit.AI Enhanced"
    app_version: str = "2.0.0"
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("production", env="ENVIRONMENT")
    
    # Server settings
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    workers: int = Field(4, env="WORKERS")
    
    # API settings
    api_prefix: str = "/api/v2"
    cors_origins: List[str] = Field(["*"], env="CORS_ORIGINS")
    rate_limit_per_minute: int = Field(60, env="RATE_LIMIT_PER_MINUTE")
    
    # Security
    secret_key: str = Field("your-secret-key-here", env="SECRET_KEY")
    api_key: Optional[str] = Field(None, env="API_KEY")
    jwt_secret: Optional[str] = Field(None, env="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(24, env="JWT_EXPIRATION_HOURS")
    
    # Database settings
    database_url: Optional[str] = Field(None, env="DATABASE_URL")
    database_pool_size: int = Field(10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis settings
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    redis_host: str = Field("localhost", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_db: int = Field(0, env="REDIS_DB")
    redis_password: Optional[str] = Field(None, env="REDIS_PASSWORD")
    
    # Cache settings
    cache_default_ttl: int = Field(3600, env="CACHE_DEFAULT_TTL")
    cache_max_size: int = Field(1000, env="CACHE_MAX_SIZE")
    cache_cleanup_interval: int = Field(300, env="CACHE_CLEANUP_INTERVAL")
    
    # Queue settings
    queue_backend: str = Field("redis", env="QUEUE_BACKEND")
    queue_max_workers: int = Field(4, env="QUEUE_MAX_WORKERS")
    queue_default_timeout: int = Field(300, env="QUEUE_DEFAULT_TIMEOUT")
    queue_retry_attempts: int = Field(3, env="QUEUE_RETRY_ATTEMPTS")
    
    # WebSocket settings
    websocket_enabled: bool = Field(True, env="WEBSOCKET_ENABLED")
    websocket_ping_interval: int = Field(30, env="WEBSOCKET_PING_INTERVAL")
    websocket_ping_timeout: int = Field(10, env="WEBSOCKET_PING_TIMEOUT")
    websocket_max_connections: int = Field(1000, env="WEBSOCKET_MAX_CONNECTIONS")
    
    # Computer Vision settings
    yolo_model_path: str = Field("yolov8n.pt", env="YOLO_MODEL_PATH")
    detection_backend: str = Field("ensemble", env="DETECTION_BACKEND")
    detection_confidence_threshold: float = Field(0.3, env="DETECTION_CONFIDENCE_THRESHOLD")
    detection_nms_threshold: float = Field(0.5, env="DETECTION_NMS_THRESHOLD")
    detection_max_detections: int = Field(100, env="DETECTION_MAX_DETECTIONS")
    
    # OCR settings
    enable_ocr: bool = Field(True, env="ENABLE_OCR")
    ocr_lang: str = Field("eng", env="OCR_LANG")
    ocr_confidence_threshold: float = Field(0.5, env="OCR_CONFIDENCE_THRESHOLD")
    
    # LLM settings
    llm_enabled: bool = Field(True, env="LLM_ENABLED")
    llm_provider: str = Field("openai", env="LLM_PROVIDER")
    llm_model: str = Field("gpt-3.5-turbo", env="LLM_MODEL")
    llm_api_key: Optional[str] = Field(None, env="LLM_API_KEY")
    llm_api_base: Optional[str] = Field(None, env="LLM_API_BASE")
    llm_max_tokens: int = Field(1000, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.7, env="LLM_TEMPERATURE")
    
    # LiteLLM settings
    litellm_enabled: bool = Field(True, env="LITELLM_ENABLED")
    litellm_api_key: Optional[str] = Field(None, env="LITELLM_API_KEY")
    litellm_api_base: Optional[str] = Field(None, env="LITELLM_API_BASE")
    litellm_model: str = Field("gpt-3.5-turbo", env="LITELLM_MODEL")
    
    # Cohere settings
    cohere_api_key: Optional[str] = Field(None, env="COHERE_API_KEY")
    cohere_model: str = Field("command", env="COHERE_MODEL")
    
    # Mistral settings
    mistral_api_key: Optional[str] = Field(None, env="MISTRAL_API_KEY")
    mistral_model: str = Field("mistral-medium", env="MISTRAL_MODEL")
    
    # Cerebras settings
    cerebras_api_key: Optional[str] = Field(None, env="CEREBRAS_API_KEY")
    cerebras_model: str = Field("cerebras-1.3b", env="CEREBRAS_MODEL")
    
    # File storage settings
    upload_dir: str = Field("uploads", env="UPLOAD_DIR")
    max_file_size: int = Field(10 * 1024 * 1024, env="MAX_FILE_SIZE")  # 10MB
    allowed_file_types: List[str] = Field(["image/jpeg", "image/png", "image/webp"], env="ALLOWED_FILE_TYPES")
    
    # Analysis settings
    analysis_timeout: int = Field(300, env="ANALYSIS_TIMEOUT")
    analysis_max_retries: int = Field(3, env="ANALYSIS_MAX_RETRIES")
    analysis_batch_size: int = Field(10, env="ANALYSIS_BATCH_SIZE")
    analysis_quality_assessment: bool = Field(True, env="ANALYSIS_QUALITY_ASSESSMENT")
    
    # Monitoring settings
    monitoring_enabled: bool = Field(True, env="MONITORING_ENABLED")
    prometheus_enabled: bool = Field(True, env="PROMETHEUS_ENABLED")
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    health_check_interval: int = Field(30, env="HEALTH_CHECK_INTERVAL")
    
    # Logging settings
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}", env="LOG_FORMAT")
    log_file: Optional[str] = Field(None, env="LOG_FILE")
    log_rotation: str = Field("1 day", env="LOG_ROTATION")
    log_retention: str = Field("30 days", env="LOG_RETENTION")
    
    # Email settings
    email_enabled: bool = Field(False, env="EMAIL_ENABLED")
    email_host: Optional[str] = Field(None, env="EMAIL_HOST")
    email_port: int = Field(587, env="EMAIL_PORT")
    email_username: Optional[str] = Field(None, env="EMAIL_USERNAME")
    email_password: Optional[str] = Field(None, env="EMAIL_PASSWORD")
    email_use_tls: bool = Field(True, env="EMAIL_USE_TLS")
    
    # Notification settings
    notifications_enabled: bool = Field(False, env="NOTIFICATIONS_ENABLED")
    slack_webhook_url: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")
    discord_webhook_url: Optional[str] = Field(None, env="DISCORD_WEBHOOK_URL")
    
    # External services
    remote_detect_url: Optional[str] = Field(None, env="REMOTE_DETECT_URL")
    remote_detect_api_key: Optional[str] = Field(None, env="REMOTE_DETECT_API_KEY")
    
    # Component database
    component_database_path: str = Field("data/content/components.yaml", env="COMPONENT_DATABASE_PATH")
    project_templates_path: str = Field("data/content/projects.yaml", env="PROJECT_TEMPLATES_PATH")
    educational_content_path: str = Field("data/content/educational.yaml", env="EDUCATIONAL_CONTENT_PATH")
    repair_guides_path: str = Field("data/content/repair.yaml", env="REPAIR_GUIDES_PATH")
    
    # Data directories
    data_dir: str = Field("data", env="DATA_DIR")
    models_dir: str = Field("models", env="MODELS_DIR")
    cache_dir: str = Field("cache", env="CACHE_DIR")
    temp_dir: str = Field("temp", env="TEMP_DIR")
    
    # Performance settings
    max_concurrent_analyses: int = Field(10, env="MAX_CONCURRENT_ANALYSES")
    analysis_memory_limit: int = Field(1024 * 1024 * 1024, env="ANALYSIS_MEMORY_LIMIT")  # 1GB
    gpu_enabled: bool = Field(True, env="GPU_ENABLED")
    gpu_memory_fraction: float = Field(0.8, env="GPU_MEMORY_FRACTION")
    
    # Feature flags
    feature_websocket: bool = Field(True, env="FEATURE_WEBSOCKET")
    feature_batch_analysis: bool = Field(True, env="FEATURE_BATCH_ANALYSIS")
    feature_educational_content: bool = Field(True, env="FEATURE_EDUCATIONAL_CONTENT")
    feature_repair_guides: bool = Field(True, env="FEATURE_REPAIR_GUIDES")
    feature_advanced_analytics: bool = Field(True, env="FEATURE_ADVANCED_ANALYTICS")
    feature_real_time_progress: bool = Field(True, env="FEATURE_REAL_TIME_PROGRESS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_redis_url(self) -> str:
        """Get Redis URL from settings."""
        if self.redis_url:
            return self.redis_url
        
        auth_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def get_database_url(self) -> str:
        """Get database URL from settings."""
        if self.database_url:
            return self.database_url
        return "sqlite:///./circuit_ai.db"
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration based on provider."""
        config = {
            "enabled": self.llm_enabled,
            "provider": self.llm_provider,
            "model": self.llm_model,
            "max_tokens": self.llm_max_tokens,
            "temperature": self.llm_temperature
        }
        
        if self.llm_provider == "openai":
            config.update({
                "api_key": self.llm_api_key,
                "api_base": self.llm_api_base
            })
        elif self.llm_provider == "cohere":
            config.update({
                "api_key": self.cohere_api_key,
                "model": self.cohere_model
            })
        elif self.llm_provider == "mistral":
            config.update({
                "api_key": self.mistral_api_key,
                "model": self.mistral_model
            })
        elif self.llm_provider == "cerebras":
            config.update({
                "api_key": self.cerebras_api_key,
                "model": self.cerebras_model
            })
        
        return config
    
    def get_detection_config(self) -> Dict[str, Any]:
        """Get detection configuration."""
        return {
            "backend": self.detection_backend,
            "confidence_threshold": self.detection_confidence_threshold,
            "nms_threshold": self.detection_nms_threshold,
            "max_detections": self.detection_max_detections,
            "model_path": self.yolo_model_path,
            "enable_ocr": self.enable_ocr,
            "ocr_lang": self.ocr_lang,
            "ocr_confidence_threshold": self.ocr_confidence_threshold
        }
    
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration."""
        return {
            "redis_url": self.get_redis_url(),
            "default_ttl": self.cache_default_ttl,
            "max_size": self.cache_max_size,
            "cleanup_interval": self.cache_cleanup_interval
        }
    
    def get_queue_config(self) -> Dict[str, Any]:
        """Get queue configuration."""
        return {
            "backend": self.queue_backend,
            "redis_url": self.get_redis_url(),
            "max_workers": self.queue_max_workers,
            "default_timeout": self.queue_default_timeout,
            "retry_attempts": self.queue_retry_attempts
        }
    
    def get_websocket_config(self) -> Dict[str, Any]:
        """Get WebSocket configuration."""
        return {
            "enabled": self.websocket_enabled and self.feature_websocket,
            "ping_interval": self.websocket_ping_interval,
            "ping_timeout": self.websocket_ping_timeout,
            "max_connections": self.websocket_max_connections
        }
    
    def validate_settings(self) -> List[str]:
        """Validate settings and return list of warnings."""
        warnings = []
        
        # Check required settings
        if not self.secret_key or self.secret_key == "your-secret-key-here":
            warnings.append("SECRET_KEY should be set to a secure value")
        
        if self.environment == "production":
            if not self.api_key:
                warnings.append("API_KEY should be set in production")
            
            if self.debug:
                warnings.append("DEBUG should be False in production")
        
        # Check LLM settings
        if self.llm_enabled:
            if not self.llm_api_key:
                warnings.append(f"LLM_API_KEY should be set for provider: {self.llm_provider}")
        
        # Check Redis settings
        if self.redis_url or self.redis_host != "localhost":
            if not self.redis_password:
                warnings.append("REDIS_PASSWORD should be set for production Redis")
        
        # Check file paths
        for path_name, path_value in [
            ("Component Database", self.component_database_path),
            ("Project Templates", self.project_templates_path),
            ("Educational Content", self.educational_content_path),
            ("Repair Guides", self.repair_guides_path)
        ]:
            if not Path(path_value).exists():
                warnings.append(f"{path_name} file not found: {path_value}")
        
        return warnings

# Global settings instance
enhanced_settings = EnhancedSettings()

# Validate settings on import
if __name__ == "__main__":
    warnings = enhanced_settings.validate_settings()
    if warnings:
        print("Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("Configuration validation passed!")

