import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import src.vision.enhanced_detector as ed


def test_detector_model_source_when_yolo_unavailable(monkeypatch):
    """
    If YOLO is unavailable, detector should mark model_source accordingly and not crash.
    """
    monkeypatch.setattr(ed, "YOLO_AVAILABLE", False)
    detector = ed.EnhancedComponentDetector()
    assert detector.model_source == "yolo-unavailable"
    assert detector.fallback_used is True
