"""
Functional planning API routes.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from src.schemas.functional import (
    FunctionalSpec, JobStatus, JobResult, 
    DesignParameters, EvaluationResult
)
from services.deterministic_engine import DeterministicEngine
from services.heuristic_planner import HeuristicPlanner
from services.evaluator.master import MasterEvaluator

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (in production, use Redis/database)
jobs: Dict[str, JobResult] = {}
job_status: Dict[str, JobStatus] = {}

# Initialize services
planner = HeuristicPlanner(seed=42)
evaluator = MasterEvaluator()
engine = DeterministicEngine(planner, evaluator)

@router.post("/v1/plan", response_model=JobStatus)
def create_plan(spec: FunctionalSpec, background_tasks: BackgroundTasks, idempotency_key: str = None):
    """
    Create a new functional planning job.
    
    Args:
        spec: Functional specification
        background_tasks: FastAPI background tasks
        idempotency_key: Optional key for idempotent operations (Circuit.AI integration)
        
    Returns:
        Job status
    """
    logger.info(f"Creating plan for spec: {spec.id}")
    
    # Use idempotency key if provided (Circuit.AI integration)
    job_key = idempotency_key if idempotency_key else spec.id
    
    # Check if job already exists
    if job_key in jobs:
        logger.info(f"Returning existing job: {job_key}")
        return job_status[job_key]
    
    # Create job status
    status = JobStatus(
        id=job_key,
        spec_id=spec.id,
        status="pending",
        max_iterations=spec.iteration_budget.max_iters
    )
    
    job_status[job_key] = status
    
    # Start optimization in background
    background_tasks.add_task(run_optimization, job_key, spec)
    
    return status

@router.get("/v1/jobs/{job_id}/status", response_model=JobStatus)
def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return job_status[job_id]

@router.get("/v1/jobs/{job_id}/result", response_model=JobResult)
def get_job_result(job_id: str):
    """Get job result"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job result {job_id} not found")
    
    return jobs[job_id]

@router.get("/v1/jobs/{job_id}/artifact")
def get_artifact(job_id: str, artifact_type: str = "stl"):
    """Download job artifact"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    if artifact_type not in job.artifacts:
        raise HTTPException(status_code=404, detail=f"Artifact type {artifact_type} not found")
    
    artifact_path = job.artifacts[artifact_type]
    
    return FileResponse(
        path=artifact_path,
        media_type="application/octet-stream",
        filename=f"{job_id}_{artifact_type}.{artifact_type}"
    )

@router.get("/v1/jobs/{job_id}/report")
def get_job_report(job_id: str):
    """Get job report"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = jobs[job_id]
    
    if not job.report:
        raise HTTPException(status_code=404, detail=f"Report not available for job {job_id}")
    
    return {"report": job.report}

@router.post("/v1/evaluate")
def evaluate_stl(stl_path: str, spec: FunctionalSpec, params: DesignParameters):
    """
    Evaluate an STL file against functional requirements.
    
    Args:
        stl_path: Path to STL file
        spec: Functional specification
        params: Design parameters
        
    Returns:
        Evaluation results
    """
    try:
        results = evaluator.evaluate(stl_path, spec, params.model_dump())
        summary = evaluator.get_summary(results)
        
        return {
            "results": [result.model_dump() for result in results],
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def run_optimization(job_id: str, spec: FunctionalSpec):
    """Run optimization in background"""
    try:
        logger.info(f"Starting optimization for job: {job_id}")
        
        # Update status to running
        if job_id in job_status:
            job_status[job_id].status = "running"
        
        # Run optimization
        result = engine.optimize(spec, output_dir="jobs")
        
        # Store result
        jobs[job_id] = result
        
        # Update final status
        if job_id in job_status:
            job_status[job_id].status = "completed" if result.success else "failed"
            job_status[job_id].best_score = max(iter.overall_score for iter in result.iterations) if result.iterations else 0.0
            job_status[job_id].all_passed = result.success
        
        logger.info(f"Optimization complete for job: {job_id}, success: {result.success}")
        
        # TODO: Send webhook notification for Circuit.AI integration
        # if result.success and webhook_url:
        #     send_webhook_notification(webhook_url, job_id, result)
        
    except Exception as e:
        logger.error(f"Optimization failed for job {job_id}: {e}")
        
        # Update status to failed
        if job_id in job_status:
            job_status[job_id].status = "failed"
            job_status[job_id].error_message = str(e)
