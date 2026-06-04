# PCB Defect Test Samples

Synthetic PCB images for testing defect detection.

## Samples:

- **good_board.jpg**: Pristine PCB with no defects
- **solder_bridge.jpg**: Solder bridge connecting pads
- **cold_joint.jpg**: Cold solder joint (dull, cracked)
- **burnt_component.jpg**: Burnt resistor with discoloration
- **missing_component.jpg**: PCB with missing resistor
- **corrosion.jpg**: Green oxidation on copper
- **broken_trace.jpg**: Broken PCB trace
- **misaligned_component.jpg**: Component not aligned to pads
- **contamination.jpg**: Flux residue contamination
- **excess_solder.jpg**: Excessive solder on pad

## Usage:

```python
from vision.defect_detector import DefectDetector
import cv2

detector = DefectDetector()
image = cv2.imread('tests/data/defect_samples/solder_bridge.jpg')
defects = detector.detect_defects(image)
```
