"""
Prometheus metrics integration for production observability.
"""

import time
import logging
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Core metrics
optimization_requests = Counter(
    'splicer_optimization_requests_total',
    'Total optimization requests',
    ['spec_id', 'status']
)

optimization_duration = Histogram(
    'splicer_optimization_duration_seconds',
    'Time spent on optimization',
    ['spec_id'],
    buckets=[1, 3, 5, 10, 15, 30, 60, 120, 300]
)

evaluation_duration = Histogram(
    'splicer_evaluation_duration_seconds',
    'Time spent on evaluation',
    ['test_type'],
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)

test_results = Counter(
    'splicer_test_results_total',
    'Test results by type and outcome',
    ['test_type', 'result']
)

satisfaction_score = Gauge(
    'splicer_satisfaction_score',
    'Final satisfaction score',
    ['spec_id', 'job_id']
)

iteration_count = Histogram(
    'splicer_iterations_total',
    'Number of iterations per optimization',
    ['spec_id'],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
)

artifact_size = Histogram(
    'splicer_artifact_size_bytes',
    'Size of generated artifacts',
    ['artifact_type'],
    buckets=[1024, 10240, 102400, 1024000, 10240000]
)

active_jobs = Gauge(
    'splicer_active_jobs',
    'Number of currently active optimization jobs'
)

cache_hits = Counter(
    'splicer_cache_hits_total',
    'Evaluation cache hits',
    ['cache_type']
)

cache_misses = Counter(
    'splicer_cache_misses_total',
    'Evaluation cache misses',
    ['cache_type']
)

class MetricsCollector:
    """Collect and expose metrics for production monitoring"""
    
    def __init__(self):
        self.start_time = time.time()
        logger.info("Metrics collector initialized")
    
    def record_optimization_start(self, spec_id: str, job_id: str):
        """Record optimization start"""
        optimization_requests.labels(spec_id=spec_id, status='started').inc()
        active_jobs.inc()
        logger.debug(f"Optimization started: {spec_id} ({job_id})")
    
    def record_optimization_complete(self, spec_id: str, job_id: str, 
                                   duration: float, success: bool, 
                                   iterations: int, satisfaction: float):
        """Record optimization completion"""
        status = 'success' if success else 'failure'
        optimization_requests.labels(spec_id=spec_id, status=status).inc()
        optimization_duration.labels(spec_id=spec_id).observe(duration)
        iteration_count.labels(spec_id=spec_id).observe(iterations)
        satisfaction_score.labels(spec_id=spec_id, job_id=job_id).set(satisfaction)
        active_jobs.dec()
        
        logger.info(f"Optimization complete: {spec_id} ({job_id}) - "
                   f"{status}, {duration:.1f}s, {iterations} iters, {satisfaction:.2f}")
    
    def record_evaluation(self, test_type: str, duration: float, passed: bool):
        """Record individual test evaluation"""
        evaluation_duration.labels(test_type=test_type).observe(duration)
        result = 'pass' if passed else 'fail'
        test_results.labels(test_type=test_type, result=result).inc()
    
    def record_artifact(self, artifact_type: str, size_bytes: int):
        """Record artifact generation"""
        artifact_size.labels(artifact_type=artifact_type).observe(size_bytes)
    
    def record_cache_event(self, cache_type: str, hit: bool):
        """Record cache hit/miss"""
        if hit:
            cache_hits.labels(cache_type=cache_type).inc()
        else:
            cache_misses.labels(cache_type=cache_type).inc()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "active_jobs": active_jobs._value._value,
            "total_requests": optimization_requests._value._value,
            "cache_hit_rate": self._calculate_cache_hit_rate()
        }
    
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate overall cache hit rate"""
        total_hits = sum(sample[2] for sample in cache_hits._metrics.values())
        total_misses = sum(sample[2] for sample in cache_misses._metrics.values())
        
        if total_hits + total_misses == 0:
            return 0.0
        
        return total_hits / (total_hits + total_misses)
    
    def generate_prometheus_metrics(self) -> str:
        """Generate Prometheus metrics output"""
        return generate_latest().decode('utf-8')

# Global metrics collector
metrics = MetricsCollector()

# Convenience decorators
def track_optimization(spec_id: str, job_id: str):
    """Decorator to track optimization metrics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            metrics.record_optimization_start(spec_id, job_id)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Extract metrics from result if available
                success = getattr(result, 'success', True)
                iterations = getattr(result, 'iterations', [])
                satisfaction = getattr(result, 'final_score', 0.0)
                
                metrics.record_optimization_complete(
                    spec_id, job_id, duration, success, 
                    len(iterations), satisfaction
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_optimization_complete(
                    spec_id, job_id, duration, False, 0, 0.0
                )
                raise
        
        return wrapper
    return decorator

def track_evaluation(test_type: str):
    """Decorator to track evaluation metrics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                results = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record metrics for each result
                if isinstance(results, list):
                    for result in results:
                        passed = getattr(result, 'passed', False)
                        metrics.record_evaluation(test_type, duration/len(results), passed)
                else:
                    passed = getattr(results, 'passed', False)
                    metrics.record_evaluation(test_type, duration, passed)
                
                return results
            except Exception as e:
                duration = time.time() - start_time
                metrics.record_evaluation(test_type, duration, False)
                raise
        
        return wrapper
    return decorator

# FastAPI integration
def setup_metrics_endpoint(app):
    """Setup Prometheus metrics endpoint"""
    from fastapi import Response
    
    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus metrics endpoint"""
        return Response(
            content=metrics.generate_prometheus_metrics(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    @app.get("/metrics/summary")
    async def metrics_summary():
        """Human-readable metrics summary"""
        return metrics.get_metrics_summary()
