"""
Production Logging Configuration

Structured logging for production environments with JSON format.
"""

import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger
import os

class ProductionLogger:
    """Production-ready logger with structured JSON output."""
    
    def __init__(self):
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging for production."""
        # Remove default handler
        logger.remove()
        
        # Add structured JSON logging
        logger.add(
            sys.stdout,
            format=self._json_formatter,
            level=os.getenv("LOG_LEVEL", "INFO"),
            serialize=False,
            colorize=False
        )
        
        # Add file logging if configured
        log_file = os.getenv("LOG_FILE")
        if log_file:
            logger.add(
                log_file,
                format=self._json_formatter,
                level=os.getenv("LOG_LEVEL", "INFO"),
                serialize=False,
                rotation="100 MB",
                retention="30 days",
                compression="gz"
            )
    
    def _json_formatter(self, record: Dict[str, Any]) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "process_id": record["process"].id,
            "thread_id": record["thread"].id
        }
        
        # Add extra fields if present
        if record.get("extra"):
            log_entry.update(record["extra"])
        
        # Add exception info if present
        if record.get("exception"):
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback
            }
        
        return json.dumps(log_entry)
    
    def log_request(
        self, 
        method: str, 
        path: str, 
        status_code: int, 
        duration: float,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log HTTP request."""
        logger.info(
            "HTTP request",
            extra={
                "event_type": "http_request",
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "user_id": user_id,
                "ip_address": ip_address
            }
        )
    
    def log_analysis(
        self,
        analysis_id: str,
        user_id: str,
        file_size: int,
        components_detected: int,
        processing_time: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Log PCB analysis event."""
        log_data = {
            "event_type": "analysis",
            "analysis_id": analysis_id,
            "user_id": user_id,
            "file_size": file_size,
            "components_detected": components_detected,
            "processing_time_ms": round(processing_time * 1000, 2),
            "success": success
        }
        
        if error:
            log_data["error"] = error
        
        if success:
            logger.info("PCB analysis completed", extra=log_data)
        else:
            logger.error("PCB analysis failed", extra=log_data)
    
    def log_billing(
        self,
        event_type: str,
        user_id: str,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        plan: Optional[str] = None,
        stripe_event_id: Optional[str] = None
    ):
        """Log billing events."""
        log_data = {
            "event_type": f"billing_{event_type}",
            "user_id": user_id,
            "stripe_event_id": stripe_event_id
        }
        
        if amount:
            log_data["amount"] = amount
        if currency:
            log_data["currency"] = currency
        if plan:
            log_data["plan"] = plan
        
        logger.info(f"Billing event: {event_type}", extra=log_data)
    
    def log_security(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security events."""
        log_data = {
            "event_type": f"security_{event_type}",
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        if details:
            log_data.update(details)
        
        logger.warning(f"Security event: {event_type}", extra=log_data)
    
    def log_performance(
        self,
        operation: str,
        duration: float,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log performance metrics."""
        log_data = {
            "event_type": "performance",
            "operation": operation,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user_id
        }
        
        if details:
            log_data.update(details)
        
        logger.info(f"Performance: {operation}", extra=log_data)

# Global logger instance
production_logger = ProductionLogger()

# Convenience functions
def log_request(method: str, path: str, status_code: int, duration: float, **kwargs):
    production_logger.log_request(method, path, status_code, duration, **kwargs)

def log_analysis(analysis_id: str, user_id: str, **kwargs):
    production_logger.log_analysis(analysis_id, user_id, **kwargs)

def log_billing(event_type: str, user_id: str, **kwargs):
    production_logger.log_billing(event_type, user_id, **kwargs)

def log_security(event_type: str, **kwargs):
    production_logger.log_security(event_type, **kwargs)

def log_performance(operation: str, duration: float, **kwargs):
    production_logger.log_performance(operation, duration, **kwargs)
