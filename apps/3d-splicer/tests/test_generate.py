import json
from pathlib import Path
import sys
import os
import re

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.template_loader import render_template
from core.cadquery_generator import script_to_stl
from core.validators import validate_stl

def test_mvp():
    """Test the complete MVP pipeline."""
    try:
        import cadquery  # type: ignore
        import trimesh  # type: ignore
    except Exception:
        import pytest

        pytest.skip("cadquery/trimesh not installed in this environment")

    # Load example description
    desc_path = Path(__file__).parent.parent / "examples" / "iphone7_desc.json"
    desc = json.loads(desc_path.read_text())
    
    # Render template
    code = render_template("phone_case.cq.j2", desc)
    assert "import cadquery" in code
    assert "result = case" in code
    
    # Generate STL
    out_path = Path("stl/test_case.stl")
    out_path.parent.mkdir(exist_ok=True)
    script_to_stl(code, out_path)
    
    # Validate STL exists
    assert out_path.exists()
    
    # Validate mesh properties
    report = validate_stl(str(out_path))
    assert report["faces"] > 0
    assert "bounds" in report
    
    # Clean up
    if out_path.exists():
        os.unlink(out_path)

def test_template_rendering():
    """Test template rendering with various inputs."""
    desc = {
        "pcb": {"width_mm": 50, "height_mm": 30, "thickness_mm": 1.0, "corner_radius_mm": 2.0},
        "enclosure": {"wall_mm": 1.5, "clearance_mm": 0.5, "lip_mm": 1.0, "fillet_mm": 0.8},
        "ports": [],
        "mounts": []
    }
    
    code = render_template("phone_case.cq.j2", desc)
    assert re.search(r"\bpcb_w\s*=\s*50\b", code)
    assert re.search(r"\bpcb_h\s*=\s*30\b", code)

if __name__ == "__main__":
    test_mvp()
    test_template_rendering()
    print("All tests passed!")
