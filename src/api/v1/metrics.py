from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from typing import Dict, Any

# Request metrics
REQUEST_COUNT = Counter(
    'circuit_api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status_code', 'user_id']
)

REQUEST_DURATION = Histogram(
    'circuit_api_request_duration_seconds',
    'API request duration in seconds',
    ['endpoint', 'method']
)

# Analysis metrics
ANALYZE_LATENCY = Histogram(
    'circuit_analyze_latency_seconds',
    'PCB analysis latency in seconds',
    ['backend', 'user_id']
)

BATCH_ANALYZE_LATENCY = Histogram(
    'circuit_batch_analyze_latency_seconds',
    'Batch PCB analysis latency in seconds',
    ['batch_size', 'user_id']
)

COMPONENTS_DETECTED = Counter(
    'circuit_components_detected_total',
    'Total number of components detected',
    ['component_type', 'user_id']
)

ANALYSIS_SUCCESS_RATE = Counter(
    'circuit_analysis_success_total',
    'Total number of successful analyses',
    ['user_id']
)

ANALYSIS_FAILURE_RATE = Counter(
    'circuit_analysis_failure_total',
    'Total number of failed analyses',
    ['user_id', 'error_type']
)

# System metrics
ACTIVE_CONNECTIONS = Gauge(
    'circuit_active_connections',
    'Number of active connections'
)

QUEUE_SIZE = Gauge(
    'circuit_queue_size',
    'Number of items in processing queue'
)

MEMORY_USAGE = Gauge(
    'circuit_memory_usage_bytes',
    'Memory usage in bytes'
)

# Business metrics
TOTAL_VALUE_ANALYZED = Counter(
    'circuit_total_value_analyzed_usd',
    'Total value of components analyzed in USD',
    ['user_id']
)

USERS_ACTIVE = Gauge(
    'circuit_users_active',
    'Number of active users'
)

API_KEY_USAGE = Counter(
    'circuit_api_key_usage_total',
    'Total API key usage',
    ['key_id', 'user_id']
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    'circuit_rate_limit_hits_total',
    'Total number of rate limit hits',
    ['user_id', 'endpoint']
)

# Error metrics
ERROR_COUNT = Counter(
    'circuit_errors_total',
    'Total number of errors',
    ['error_type', 'endpoint']
)

# Database metrics
DATABASE_QUERY_DURATION = Histogram(
    'circuit_database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type']
)

DATABASE_CONNECTIONS = Gauge(
    'circuit_database_connections',
    'Number of database connections'
)

# File processing metrics
FILE_SIZE_PROCESSED = Histogram(
    'circuit_file_size_bytes',
    'Size of processed files in bytes',
    ['file_type']
)

PROCESSING_TIME = Summary(
    'circuit_processing_time_seconds',
    'Time spent processing files',
    ['processing_stage']
)

# Model performance metrics
MODEL_INFERENCE_TIME = Histogram(
    'circuit_model_inference_time_seconds',
    'Model inference time in seconds',
    ['model_name', 'model_version']
)

MODEL_CONFIDENCE = Histogram(
    'circuit_model_confidence',
    'Model confidence scores',
    ['model_name', 'component_type']
)

# Cache metrics
CACHE_HITS = Counter(
    'circuit_cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

CACHE_MISSES = Counter(
    'circuit_cache_misses_total',
    'Total number of cache misses',
    ['cache_type']
)

CACHE_SIZE = Gauge(
    'circuit_cache_size_bytes',
    'Cache size in bytes',
    ['cache_type']
)

# WebSocket metrics
WEBSOCKET_CONNECTIONS = Gauge(
    'circuit_websocket_connections',
    'Number of active WebSocket connections'
)

WEBSOCKET_MESSAGES = Counter(
    'circuit_websocket_messages_total',
    'Total number of WebSocket messages',
    ['message_type']
)

# Custom metrics for Circuit.AI specific features
EDUCATIONAL_CONTENT_ACCESSED = Counter(
    'circuit_educational_content_accessed_total',
    'Total number of educational content accesses',
    ['content_type', 'user_id']
)

PROJECT_RECOMMENDATIONS_GENERATED = Counter(
    'circuit_project_recommendations_generated_total',
    'Total number of project recommendations generated',
    ['difficulty_level', 'user_id']
)

COMPONENT_VALUE_ESTIMATED = Counter(
    'circuit_component_value_estimated_total',
    'Total number of component value estimations',
    ['component_type', 'user_id']
)

# Utility functions for metrics
def record_request_metrics(endpoint: str, method: str, status_code: int, duration: float, user_id: str = "anonymous"):
    """Record request metrics."""
    REQUEST_COUNT.labels(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        user_id=user_id
    ).inc()
    
    REQUEST_DURATION.labels(
        endpoint=endpoint,
        method=method
    ).observe(duration)

def record_analysis_metrics(backend: str, duration: float, components: list, success: bool, user_id: str = "anonymous", error_type: str = None):
    """Record analysis metrics."""
    if success:
        ANALYSIS_SUCCESS_RATE.labels(user_id=user_id).inc()
        ANALYZE_LATENCY.labels(backend=backend, user_id=user_id).observe(duration)
        
        # Record component detection
        for component in components:
            COMPONENTS_DETECTED.labels(
                component_type=component.get('type', 'unknown'),
                user_id=user_id
            ).inc()
    else:
        ANALYSIS_FAILURE_RATE.labels(
            user_id=user_id,
            error_type=error_type or 'unknown'
        ).inc()

def record_batch_analysis_metrics(batch_size: int, duration: float, user_id: str = "anonymous"):
    """Record batch analysis metrics."""
    BATCH_ANALYZE_LATENCY.labels(
        batch_size=str(batch_size),
        user_id=user_id
    ).observe(duration)

def record_component_value(value: float, component_type: str, user_id: str = "anonymous"):
    """Record component value estimation."""
    TOTAL_VALUE_ANALYZED.labels(user_id=user_id).inc(value)
    COMPONENT_VALUE_ESTIMATED.labels(
        component_type=component_type,
        user_id=user_id
    ).inc()

def record_educational_access(content_type: str, user_id: str = "anonymous"):
    """Record educational content access."""
    EDUCATIONAL_CONTENT_ACCESSED.labels(
        content_type=content_type,
        user_id=user_id
    ).inc()

def record_project_recommendation(difficulty_level: str, user_id: str = "anonymous"):
    """Record project recommendation generation."""
    PROJECT_RECOMMENDATIONS_GENERATED.labels(
        difficulty_level=difficulty_level,
        user_id=user_id
    ).inc()

def record_model_metrics(model_name: str, model_version: str, inference_time: float, confidence: float, component_type: str = None):
    """Record model performance metrics."""
    MODEL_INFERENCE_TIME.labels(
        model_name=model_name,
        model_version=model_version
    ).observe(inference_time)
    
    if component_type:
        MODEL_CONFIDENCE.labels(
            model_name=model_name,
            component_type=component_type
        ).observe(confidence)

def record_cache_metrics(cache_type: str, hit: bool):
    """Record cache metrics."""
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()

def record_websocket_metrics(message_type: str):
    """Record WebSocket metrics."""
    WEBSOCKET_MESSAGES.labels(message_type=message_type).inc()

def record_error_metrics(error_type: str, endpoint: str):
    """Record error metrics."""
    ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()

def record_database_metrics(query_type: str, duration: float):
    """Record database metrics."""
    DATABASE_QUERY_DURATION.labels(query_type=query_type).observe(duration)

def record_file_metrics(file_size: int, file_type: str):
    """Record file processing metrics."""
    FILE_SIZE_PROCESSED.labels(file_type=file_type).observe(file_size)

def record_processing_metrics(stage: str, duration: float):
    """Record processing stage metrics."""
    PROCESSING_TIME.labels(processing_stage=stage).observe(duration)

# System health metrics
def update_system_metrics():
    """Update system health metrics."""
    import psutil
    import os
    
    # Update memory usage
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    MEMORY_USAGE.set(memory_info.rss)
    
    # Update active connections (mock for now)
    ACTIVE_CONNECTIONS.set(10)  # Replace with actual connection count
    
    # Update queue size (mock for now)
    QUEUE_SIZE.set(0)  # Replace with actual queue size
    
    # Update database connections (mock for now)
    DATABASE_CONNECTIONS.set(5)  # Replace with actual connection count

# Metrics endpoint
def get_metrics_response() -> Response:
    """Get Prometheus metrics response."""
    update_system_metrics()
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Custom metrics for Circuit.AI dashboard
def get_circuit_ai_metrics() -> Dict[str, Any]:
    """Get Circuit.AI specific metrics for dashboard."""
    return {
        "total_analyses": ANALYSIS_SUCCESS_RATE._value.sum(),
        "total_components_detected": COMPONENTS_DETECTED._value.sum(),
        "total_value_analyzed": TOTAL_VALUE_ANALYZED._value.sum(),
        "active_users": USERS_ACTIVE._value,
        "average_analysis_time": ANALYZE_LATENCY._sum / max(ANALYZE_LATENCY._count, 1),
        "success_rate": ANALYSIS_SUCCESS_RATE._value.sum() / max(
            ANALYSIS_SUCCESS_RATE._value.sum() + ANALYSIS_FAILURE_RATE._value.sum(), 1
        )
    }
