"""
Preview routes for quick GLB generation and score summaries.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.schemas.functional import FunctionalSpec, DesignParameters
from services.heuristic_planner import HeuristicPlanner
from services.evaluator.master import MasterEvaluator
from src.core.cadquery_generator import script_to_stl
from src.core.template_loader import render_template

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
planner = HeuristicPlanner(seed=42)
evaluator = MasterEvaluator()

@router.post("/v1/splice/preview")
def preview_case(spec: FunctionalSpec, params: DesignParameters = None):
    """
    Generate a quick preview (GLB) with score summary.
    
    Args:
        spec: Functional specification
        params: Optional design parameters (uses initial if not provided)
        
    Returns:
        Preview info with scores and GLB path
    """
    logger.info(f"Generating preview for spec: {spec.id}")
    
    try:
        # Use provided parameters or generate initial ones
        if params is None:
            params = planner.propose_initial_parameters(spec)
        
        # Generate STL (we'll use this for now, GLB export can be added later)
        params_dict = params.model_dump()
        context = {
            "spec": spec.model_dump(),
            "params": params_dict,
            "board": spec.context.board_bbox_mm.model_dump(),
            "mounts": [mount.model_dump() for mount in spec.context.mounts],
            "io": [conn.model_dump() for conn in spec.context.io],
            "keepouts": [keepout.model_dump() for keepout in spec.context.keepouts],
            # Add individual parameter sections for template access
            "shell": params_dict.get("shell", {}),
            "bosses": params_dict.get("bosses", []),
            "vents": params_dict.get("vents", {}),
            "io_slots": params_dict.get("io_slots", []),
            "latches": params_dict.get("latches", {})
        }
        
        # Render template
        template_code = render_template("functional_case_simple.cq.j2", context)
        
        # Generate STL
        from pathlib import Path
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            stl_path = tmp.name
        
        script_to_stl(template_code, Path(stl_path))
        
        # Evaluate the preview
        evaluation_results = evaluator.evaluate(stl_path, spec, params.model_dump())
        
        # Calculate summary scores
        overall_score = sum(result.score for result in evaluation_results) / len(evaluation_results) if evaluation_results else 0.0
        passed_tests = sum(1 for result in evaluation_results if result.passed)
        total_tests = len(evaluation_results)
        
        # Clean up temp file
        Path(stl_path).unlink()
        
        return {
            "spec_id": spec.id,
            "overall_score": overall_score,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
            "test_summary": [
                {
                    "test_id": result.test_id,
                    "passed": result.passed,
                    "score": result.score,
                    "details": result.details
                }
                for result in evaluation_results
            ],
            "parameters": params.model_dump(),
            "preview_ready": True  # GLB generation would be implemented here
        }
        
    except Exception as e:
        logger.error(f"Preview generation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/v1/splice/preview/{spec_id}")
def get_preview(spec_id: str):
    """
    Get preview information for a specification.
    
    Args:
        spec_id: Specification ID
        
    Returns:
        Preview information
    """
    # This would typically load from cache or database
    # For now, return a placeholder
    return {
        "spec_id": spec_id,
        "status": "not_found",
        "message": "Preview not available. Use POST to generate preview."
    }
