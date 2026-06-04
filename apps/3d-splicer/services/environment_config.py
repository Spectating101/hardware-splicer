"""
Environment configuration for production deployment.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class EnvironmentConfig:
    """Production environment configuration with sensible defaults"""
    
    def __init__(self):
        # Runtime configuration
        self.artifact_dir = os.getenv("ARTIFACT_DIR", "/app/artifacts")
        self.max_iters = int(os.getenv("MAX_ITERS", "5"))
        self.iter_timeout_s = int(os.getenv("ITER_TIMEOUT_S", "30"))
        self.job_timeout_s = int(os.getenv("JOB_TIMEOUT_S", "180"))
        
        # Security settings
        self.trusted_templates_only = os.getenv("TRUSTED_TEMPLATES_ONLY", "true").lower() == "true"
        self.max_payload_size = int(os.getenv("MAX_PAYLOAD_SIZE", "1048576"))  # 1MB
        self.cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
        
        # Evaluation configuration
        self.must_pass_tests = os.getenv("MUST_PASS", "fit,printability").split(",")
        
        # Load weights from environment
        weights_str = os.getenv("WEIGHTS", '{"fit":2.0,"printability":2.0,"io":1.5,"drop_proxy":1.0,"thermal":0.5}')
        try:
            self.weights = json.loads(weights_str)
        except json.JSONDecodeError:
            logger.warning("Invalid WEIGHTS JSON, using defaults")
            self.weights = {"fit": 2.0, "printability": 2.0, "io": 1.5, "drop_proxy": 1.0, "thermal": 0.5}
        
        # Idempotency
        self.idempotency_enabled = os.getenv("IDEMPOTENCY", "on").lower() == "on"
        
        # Storage configuration
        self.prune_intermediate_stls = os.getenv("PRUNE_INTERMEDIATE_STLS", "true").lower() == "true"
        self.keep_final_artifacts = os.getenv("KEEP_FINAL_ARTIFACTS", "true").lower() == "true"
        
        # Observability
        self.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        
        logger.info(f"Environment config loaded: max_iters={self.max_iters}, "
                   f"job_timeout={self.job_timeout_s}s, must_pass={self.must_pass_tests}")
    
    def validate_config(self) -> bool:
        """Validate configuration settings"""
        issues = []
        
        # Validate numeric ranges
        if self.max_iters < 1 or self.max_iters > 10:
            issues.append(f"MAX_ITERS must be 1-10, got {self.max_iters}")
        
        if self.iter_timeout_s < 5 or self.iter_timeout_s > 120:
            issues.append(f"ITER_TIMEOUT_S must be 5-120, got {self.iter_timeout_s}")
        
        if self.job_timeout_s < 30 or self.job_timeout_s > 600:
            issues.append(f"JOB_TIMEOUT_S must be 30-600, got {self.job_timeout_s}")
        
        # Validate weights
        for domain, weight in self.weights.items():
            if not isinstance(weight, (int, float)) or weight < 0:
                issues.append(f"Weight for {domain} must be non-negative number, got {weight}")
        
        # Validate must-pass tests
        valid_tests = {"fit", "printability", "io", "drop_proxy", "thermal", "accessibility"}
        for test in self.must_pass_tests:
            if test not in valid_tests:
                issues.append(f"Invalid must-pass test: {test}")
        
        if issues:
            logger.error(f"Configuration validation failed: {issues}")
            return False
        
        logger.info("Configuration validation passed")
        return True
    
    def get_artifact_path(self, job_id: str, iteration: int = None, artifact_type: str = None) -> str:
        """Generate versioned artifact path"""
        base_path = f"{self.artifact_dir}/{job_id}"
        
        if iteration is not None:
            base_path += f"/iter_{iteration:02d}"
        
        if artifact_type:
            base_path += f"/{artifact_type}"
        
        return base_path
    
    def should_prune_artifact(self, artifact_path: str, is_final: bool = False) -> bool:
        """Determine if artifact should be pruned"""
        if not self.prune_intermediate_stls:
            return False
        
        if is_final:
            return False
        
        # Prune intermediate STLs but keep GLBs and reports
        if artifact_path.endswith('.stl') and 'final' not in artifact_path:
            return True
        
        return False

# Global config instance
config = EnvironmentConfig()
