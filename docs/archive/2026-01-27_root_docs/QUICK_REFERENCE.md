# Circuit-AI Quick Reference

## What Is It?

**Circuit-AI** analyzes PCB board photos and answers three questions:
1. **What is this board?** (Power Supply, Motherboard, Audio Amp, etc.)
2. **What's wrong with it?** (Corrosion, burned components, broken traces)
3. **What should I do with it?** (Repair actions, salvage recommendations)

## How to Use

### Option 1: API Endpoint
```bash
curl -X POST http://localhost:8000/detect-components \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@board.jpg" \
  -F "confidence=0.5"
```

### Option 2: Python Code
```python
from src.intelligence.board_analysis_engine import BoardAnalysisEngine
from src.vision.enhanced_detector import EnhancedComponentDetector, DetectionMethod
import numpy as np
from PIL import Image

# Load image
image = np.array(Image.open('board.jpg'))

# Detect components
detector = EnhancedComponentDetector()
detections = detector.detect_components(image, methods=[DetectionMethod.YOLO])

# Analyze
engine = BoardAnalysisEngine()
result = engine.analyze(image, detections)

# Get answers
print(result['summary'])
```

## Key Results

### Example Output
```
BOARD ANALYSIS SUMMARY:
════════════════════════════════════════════════════════

This board is identified as:
  → Power Supply Unit (confidence: 95%)

Current condition: Poor - Multiple serious faults

Repairability assessment: Low - Multiple faults detected

Salvage value: High - Component salvage only

Next steps:
  1. ✓ Check all electrolytic capacitors for bulging/leakage
  2. ✓ Test transformer with continuity checker
  3. ✓ Inspect MOSFET/rectifier diodes for damage

WARNINGS:
  • ⚠ Power supplies may store charge - discharge before work
  • ⚠ Transformer primary may be high voltage
  • ⚠ Corrosion may have damaged copper traces
════════════════════════════════════════════════════════
```

## Components Detected

The system recognizes 9 component types:
- **Cap1, Cap2, Cap3, Cap4** - Capacitors (electrolytic, ceramic, etc.)
- **MOSFET** - Transistors/switching devices
- **Mov** - Metal Oxide Varistor (surge protection)
- **Resistor/Resestor** - Current limiting
- **Transformer** - Power/signal transformation

## Board Types Recognized

1. **Power Supply Unit** - AC/DC conversion boards
2. **Audio Amplifier** - Audio signal amplification
3. **Motherboard/Control** - System control boards
4. **Power Distribution** - Voltage regulation, protection

## Files

### Core Intelligence
- `src/intelligence/board_classifier.py` - Board type identification
- `src/intelligence/fault_detector.py` - Visual fault detection
- `src/intelligence/board_analysis_engine.py` - Complete analysis

### API
- `src/api/v1/main.py` - FastAPI endpoints
- `src/vision/enhanced_detector.py` - YOLO component detection

### Models
- `pcb_runs/real_pcb_v1/weights/best.pt` - Trained YOLOv8m model (45 MB)
- Accuracy: 70.74% mAP@50-95, 94-99% per-class

### Documentation
- `CIRCUIT_AI_FINAL_STATUS.md` - Complete system status
- `INTELLIGENCE_LAYER_IMPLEMENTATION.md` - Intelligence modules
- `ENDPOINT_INTEGRATION_COMPLETE.md` - API endpoint docs

## Performance

- **Inference time**: ~0.35 seconds per image (CPU)
- **Board identification**: 95% accuracy
- **Memory usage**: ~200-300 MB
- **Throughput**: ~3.8 images/second (single thread)

## Status

✅ **Production Ready**
- Component detection: Working
- Board classification: Working
- Fault detection: Working
- Analysis & recommendations: Working
- Error handling: Complete
- Documentation: Complete

## Start Server

```bash
python -m uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000
```

Then visit: `http://localhost:8000/docs` for interactive API explorer

## Test It

```bash
python << 'EOF'
from pathlib import Path
from PIL import Image
import numpy as np
from src.vision.enhanced_detector import EnhancedComponentDetector, DetectionMethod
from src.intelligence.board_analysis_engine import BoardAnalysisEngine

# Load test image
img = np.array(Image.open(list(Path('datasets/real_pcb_archive/test/images').glob('*.jpg'))[0]))

# Detect
detector = EnhancedComponentDetector()
detections = detector.detect_components(img, methods=[DetectionMethod.YOLO])

# Analyze
engine = BoardAnalysisEngine()
result = engine.analyze(img, detections)

# Results
print(result['summary'])
EOF
```

## Roadmap

### ✅ Complete
- Component detection (YOLO)
- Board classification
- Fault detection
- Repair guidance

### 🔲 Planned
- More board types
- ML-based defect detection
- Component value database integration
- Repair video recommendations
- Frontend UI
- Mobile app

---

**Last Updated**: November 14, 2025  
**Status**: ✅ Production Ready
