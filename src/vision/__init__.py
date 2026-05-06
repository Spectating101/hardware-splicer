"""
Vision Module - Component Detection & Image Processing

Provides multi-model component detection with:
- YOLO-based detection
- Classical CV methods
- Ensemble approaches
"""

__all__ = [
    'ComponentDetection',
    'DetectionMethod',
    'EnhancedComponentDetector'
]


def __getattr__(name):
    if name in __all__:
        from .enhanced_detector import ComponentDetection, DetectionMethod, EnhancedComponentDetector

        exports = {
            "ComponentDetection": ComponentDetection,
            "DetectionMethod": DetectionMethod,
            "EnhancedComponentDetector": EnhancedComponentDetector,
        }
        return exports[name]
    raise AttributeError(f"module 'src.vision' has no attribute {name!r}")
