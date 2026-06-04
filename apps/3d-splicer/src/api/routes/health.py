# src/api/routes/health.py
from fastapi import APIRouter
import tempfile
import os

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True}

@router.get("/health/geom")
def health_geom():
    import cadquery as cq
    from cadquery import exporters
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "probe.stl")
        shape = cq.Workplane("XY").box(10, 20, 3)
        exporters.export(shape, path)
        size = os.path.getsize(path)
    return {"ok": True, "bytes": size}

@router.get("/health/evaluator")
def health_evaluator():
    """Test evaluator with synthetic spec and return expected margins"""
    try:
        import json
        import time
        from src.schemas.functional import FunctionalSpec, Context, BoundingBox, Materials, Tolerances, IterationBudget, Outputs
        
        # Create synthetic test spec
        test_spec = FunctionalSpec(
            id="health_test",
            context=Context(
                board_bbox_mm=BoundingBox(x=50, y=30, z=5),
                mounts=[],
                keepouts=[],
                io=[]
            ),
            functional_requirements=[],
            constraints=[],
            materials=Materials(primary="PLA", infill_pct=20, layer_height_mm=0.2),
            tolerances=Tolerances(fit_mm=0.3, hole_dia_mm=0.2),
            iteration_budget=IterationBudget(max_iters=1, max_seconds=30),
            outputs=Outputs(stl=True, glb_preview=False, report="json")
        )
        
        # Generate a simple test STL
        import cadquery as cq
        from cadquery import exporters
        
        with tempfile.TemporaryDirectory() as td:
            test_stl = os.path.join(td, "test.stl")
            shape = cq.Workplane("XY").box(55, 35, 8)  # Slightly larger than board
            exporters.export(shape, test_stl)
            
            # Test evaluator
            from services.evaluator.master import MasterEvaluator
            evaluator = MasterEvaluator()
            
            start_time = time.time()
            results = evaluator.evaluate(test_stl, test_spec, {})
            eval_time = time.time() - start_time
            
            # Extract margins
            margins = {}
            for result in results:
                if result.margin is not None:
                    margins[result.test_id] = result.margin
            
            return {
                "ok": True,
                "eval_time_s": eval_time,
                "tests_run": len(results),
                "expected_margins": margins,
                "stl_size_bytes": os.path.getsize(test_stl)
            }
    
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "eval_time_s": 0,
            "tests_run": 0,
            "expected_margins": {},
            "stl_size_bytes": 0
        }
