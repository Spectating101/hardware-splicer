import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Callable, Coroutine
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from loguru import logger
import threading
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory queue only")

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Job:
    id: str
    task_type: str
    payload: Dict[str, Any]
    status: JobStatus
    priority: JobPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    progress: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class QueueService:
    """Advanced job queue service with Redis and in-memory fallback."""
    
    def __init__(self, redis_url: Optional[str] = None, max_workers: int = 4):
        self.max_workers = max_workers
        self.jobs: Dict[str, Job] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.workers: List[threading.Thread] = []
        self.running = False
        self._lock = threading.Lock()
        self._condition = threading.Condition()
        
        # Initialize Redis if available
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Redis queue initialized successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using in-memory queue")
                self.redis_client = None
        else:
            logger.info("Using in-memory queue only")
        
        # Statistics
        self.stats = {
            "jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_cancelled": 0,
            "total_processing_time": 0.0
        }
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a task handler function."""
        self.task_handlers[task_type] = handler
        logger.info(f"Registered task handler for: {task_type}")
    
    def submit_job(self, task_type: str, payload: Dict[str, Any], 
                   priority: JobPriority = JobPriority.NORMAL,
                   max_retries: int = 3) -> str:
        """Submit a new job to the queue."""
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            task_type=task_type,
            payload=payload,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=datetime.now(),
            max_retries=max_retries
        )
        
        # Store in Redis if available
        if self.redis_client:
            try:
                job_data = asdict(job)
                job_data["status"] = job.status.value
                job_data["priority"] = job.priority.value
                job_data["created_at"] = job.created_at.isoformat()
                if job.started_at:
                    job_data["started_at"] = job.started_at.isoformat()
                if job.completed_at:
                    job_data["completed_at"] = job.completed_at.isoformat()
                
                self.redis_client.hset(f"job:{job_id}", mapping=job_data)
                self.redis_client.zadd("job_queue", {job_id: priority.value})
            except Exception as e:
                logger.error(f"Error storing job in Redis: {e}")
        
        # Store in memory
        with self._lock:
            self.jobs[job_id] = job
            self.stats["jobs_created"] += 1
        
        # Notify workers
        with self._condition:
            self._condition.notify()
        
        logger.info(f"Job {job_id} submitted: {task_type}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        # Try Redis first
        if self.redis_client:
            try:
                job_data = self.redis_client.hgetall(f"job:{job_id}")
                if job_data:
                    job = Job(
                        id=job_data[b"id"].decode(),
                        task_type=job_data[b"task_type"].decode(),
                        payload=json.loads(job_data[b"payload"].decode()),
                        status=JobStatus(job_data[b"status"].decode()),
                        priority=JobPriority(int(job_data[b"priority"])),
                        created_at=datetime.fromisoformat(job_data[b"created_at"].decode()),
                        max_retries=int(job_data[b"max_retries"]),
                        progress=float(job_data[b"progress"])
                    )
                    
                    if b"started_at" in job_data:
                        job.started_at = datetime.fromisoformat(job_data[b"started_at"].decode())
                    if b"completed_at" in job_data:
                        job.completed_at = datetime.fromisoformat(job_data[b"completed_at"].decode())
                    if b"result" in job_data:
                        job.result = json.loads(job_data[b"result"].decode())
                    if b"error" in job_data:
                        job.error = job_data[b"error"].decode()
                    
                    return job
            except Exception as e:
                logger.error(f"Error getting job from Redis: {e}")
        
        # Fallback to memory
        with self._lock:
            return self.jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        job = self.get_job(job_id)
        if job and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            
            # Update Redis
            if self.redis_client:
                try:
                    self.redis_client.hset(f"job:{job_id}", "status", JobStatus.CANCELLED.value)
                    self.redis_client.hset(f"job:{job_id}", "completed_at", job.completed_at.isoformat())
                    self.redis_client.zrem("job_queue", job_id)
                except Exception as e:
                    logger.error(f"Error updating job in Redis: {e}")
            
            # Update memory
            with self._lock:
                self.jobs[job_id] = job
                self.stats["jobs_cancelled"] += 1
            
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            pending = sum(1 for job in self.jobs.values() if job.status == JobStatus.PENDING)
            running = sum(1 for job in self.jobs.values() if job.status == JobStatus.RUNNING)
            completed = sum(1 for job in self.jobs.values() if job.status == JobStatus.COMPLETED)
            failed = sum(1 for job in self.jobs.values() if job.status == JobStatus.FAILED)
            
            return {
                **self.stats,
                "pending_jobs": pending,
                "running_jobs": running,
                "completed_jobs": completed,
                "failed_jobs": failed,
                "total_jobs": len(self.jobs),
                "active_workers": len([w for w in self.workers if w.is_alive()]),
                "redis_available": self.redis_client is not None
            }
    
    def _get_next_job(self) -> Optional[Job]:
        """Get the next job from the queue."""
        # Try Redis first
        if self.redis_client:
            try:
                job_ids = self.redis_client.zrange("job_queue", 0, 0, desc=True)
                if job_ids:
                    job_id = job_ids[0].decode()
                    job = self.get_job(job_id)
                    if job and job.status == JobStatus.PENDING:
                        return job
            except Exception as e:
                logger.error(f"Error getting next job from Redis: {e}")
        
        # Fallback to memory
        with self._lock:
            pending_jobs = [
                job for job in self.jobs.values()
                if job.status == JobStatus.PENDING
            ]
            
            if pending_jobs:
                # Sort by priority (highest first) and creation time
                pending_jobs.sort(
                    key=lambda j: (j.priority.value, j.created_at),
                    reverse=True
                )
                return pending_jobs[0]
        
        return None
    
    def _process_job(self, job: Job):
        """Process a job."""
        try:
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            # Update Redis
            if self.redis_client:
                try:
                    self.redis_client.hset(f"job:{job.id}", "status", JobStatus.RUNNING.value)
                    self.redis_client.hset(f"job:{job.id}", "started_at", job.started_at.isoformat())
                    self.redis_client.zrem("job_queue", job.id)
                except Exception as e:
                    logger.error(f"Error updating job in Redis: {e}")
            
            # Update memory
            with self._lock:
                self.jobs[job.id] = job
            
            # Execute task
            handler = self.task_handlers.get(job.task_type)
            if handler:
                start_time = time.time()
                result = handler(job.payload)
                processing_time = time.time() - start_time
                
                # Update job with result
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                job.result = result
                job.progress = 1.0
                
                # Update statistics
                with self._lock:
                    self.stats["jobs_completed"] += 1
                    self.stats["total_processing_time"] += processing_time
                
                logger.info(f"Job {job.id} completed successfully in {processing_time:.2f}s")
            else:
                raise Exception(f"No handler registered for task type: {job.task_type}")
                
        except Exception as e:
            # Handle job failure
            job.error = str(e)
            job.retries += 1
            
            if job.retries < job.max_retries:
                # Retry job
                job.status = JobStatus.PENDING
                logger.warning(f"Job {job.id} failed, retrying ({job.retries}/{job.max_retries}): {e}")
                
                # Re-add to queue
                if self.redis_client:
                    try:
                        self.redis_client.hset(f"job:{job.id}", "status", JobStatus.PENDING.value)
                        self.redis_client.hset(f"job:{job.id}", "retries", job.retries)
                        self.redis_client.zadd("job_queue", {job.id: job.priority.value})
                    except Exception as redis_error:
                        logger.error(f"Error re-adding job to Redis: {redis_error}")
            else:
                # Job failed permanently
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now()
                
                with self._lock:
                    self.stats["jobs_failed"] += 1
                
                logger.error(f"Job {job.id} failed permanently after {job.max_retries} retries: {e}")
            
            # Update Redis
            if self.redis_client:
                try:
                    self.redis_client.hset(f"job:{job.id}", "status", job.status.value)
                    self.redis_client.hset(f"job:{job.id}", "error", job.error)
                    self.redis_client.hset(f"job:{job.id}", "retries", job.retries)
                    if job.completed_at:
                        self.redis_client.hset(f"job:{job.id}", "completed_at", job.completed_at.isoformat())
                except Exception as redis_error:
                    logger.error(f"Error updating failed job in Redis: {redis_error}")
        
        # Update memory
        with self._lock:
            self.jobs[job.id] = job
    
    def _worker_loop(self):
        """Worker thread loop."""
        while self.running:
            job = None
            
            with self._condition:
                job = self._get_next_job()
                if not job:
                    self._condition.wait(timeout=1.0)
                    continue
            
            if job:
                self._process_job(job)
    
    def start_workers(self):
        """Start worker threads."""
        if self.running:
            return
        
        self.running = True
        self.workers = []
        
        for i in range(self.max_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"QueueWorker-{i}")
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.max_workers} queue workers")
    
    def stop_workers(self):
        """Stop worker threads."""
        self.running = False
        
        with self._condition:
            self._condition.notify_all()
        
        for worker in self.workers:
            worker.join(timeout=5.0)
        
        logger.info("Queue workers stopped")

# Global queue service instance
queue_service = QueueService()

# Register default task handlers
def register_default_handlers():
    """Register default task handlers."""
    
    def batch_analysis_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch analysis tasks."""
        # This would integrate with the existing analysis pipeline
        logger.info(f"Processing batch analysis: {payload}")
        return {"status": "completed", "results": []}
    
    def data_export_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data export tasks."""
        logger.info(f"Processing data export: {payload}")
        return {"status": "completed", "export_url": "example.com/export"}
    
    def cleanup_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cleanup tasks."""
        logger.info(f"Processing cleanup: {payload}")
        return {"status": "completed", "cleaned_items": 0}
    
    queue_service.register_task_handler("batch_analysis", batch_analysis_handler)
    queue_service.register_task_handler("data_export", data_export_handler)
    queue_service.register_task_handler("cleanup", cleanup_handler)

# Initialize default handlers
register_default_handlers()
