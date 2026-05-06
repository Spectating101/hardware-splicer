import numpy as np

from src.vision.golden_reference import GoldenReferenceInspector


def test_golden_reference_passes_identical_image():
    image = np.zeros((160, 220, 3), dtype=np.uint8)
    image[:, :] = [40, 120, 45]
    inspector = GoldenReferenceInspector()

    result = inspector.compare(image, image.copy())

    assert result["status"] == "PASS"
    assert result["defect_count"] == 0


def test_golden_reference_flags_missing_component_like_change():
    golden = np.zeros((160, 220, 3), dtype=np.uint8)
    golden[:, :] = [40, 120, 45]
    current = golden.copy()
    golden[30:60, 40:90] = [35, 35, 35]
    current[30:60, 40:90] = [40, 120, 45]
    inspector = GoldenReferenceInspector()

    result = inspector.compare(golden, current)

    assert result["status"] == "FAIL"
    assert result["defect_count"] >= 1
    assert result["defects"][0]["defect_type"] in {"missing_component", "golden_mismatch"}
