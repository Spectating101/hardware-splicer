"""
Generate synthetic PCB test images for golden dataset.

Creates sample images with various defects for testing defect detection.
"""

import numpy as np
import cv2
from pathlib import Path


def create_base_pcb(width=800, height=600):
    """Create base PCB substrate (green FR-4)."""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = [50, 120, 50]  # Green PCB substrate
    return image


def add_components(image):
    """Add typical PCB components to the image."""
    # Resistors (brown body with colored bands)
    cv2.rectangle(image, (100, 100), (150, 120), (139, 69, 19), -1)
    cv2.rectangle(image, (100, 200), (150, 220), (139, 69, 19), -1)

    # Capacitors (silver/gray)
    cv2.rectangle(image, (200, 150), (250, 170), (200, 200, 200), -1)
    cv2.rectangle(image, (200, 250), (250, 270), (200, 200, 200), -1)

    # ICs (black rectangular)
    cv2.rectangle(image, (300, 200), (340, 250), (30, 30, 30), -1)
    cv2.rectangle(image, (400, 100), (450, 150), (30, 30, 30), -1)

    # LEDs (colored epoxy)
    cv2.circle(image, (500, 150), 8, (0, 0, 200), -1)  # Red LED
    cv2.circle(image, (550, 150), 8, (0, 200, 0), -1)  # Green LED

    # Solder pads (copper/gold color)
    pad_color = (100, 180, 220)  # Golden/copper
    cv2.circle(image, (120, 110), 3, pad_color, -1)
    cv2.circle(image, (140, 110), 3, pad_color, -1)
    cv2.circle(image, (220, 160), 3, pad_color, -1)
    cv2.circle(image, (240, 160), 3, pad_color, -1)

    return image


def add_traces(image):
    """Add PCB traces (copper paths)."""
    trace_color = (80, 150, 180)  # Copper color
    cv2.line(image, (120, 110), (220, 160), trace_color, 2)
    cv2.line(image, (140, 110), (240, 160), trace_color, 2)
    cv2.line(image, (320, 225), (420, 125), trace_color, 2)
    return image


def create_good_board():
    """Create a pristine PCB with no defects."""
    image = create_base_pcb()
    image = add_components(image)
    image = add_traces(image)
    return image


def create_solder_bridge():
    """Create PCB with solder bridge defect."""
    image = create_good_board()
    # Add solder bridge (silver blob connecting two pads)
    cv2.ellipse(image, (180, 135), (30, 8), 0, 0, 360, (200, 200, 200), -1)
    return image


def create_cold_joint():
    """Create PCB with cold solder joint."""
    image = create_good_board()
    # Cold joint appears dull and has cracks
    cv2.circle(image, (240, 160), 5, (120, 120, 120), -1)  # Dull gray
    # Add crack lines
    cv2.line(image, (237, 157), (243, 163), (80, 80, 80), 1)
    return image


def create_burnt_component():
    """Create PCB with burnt component."""
    image = create_good_board()
    # Burn mark on resistor (dark brown/black)
    cv2.circle(image, (125, 110), 12, (10, 10, 10), -1)
    # Add slight brown discoloration around it
    cv2.circle(image, (125, 110), 18, (40, 30, 10), 2)
    return image


def create_missing_component():
    """Create PCB with missing component."""
    image = create_base_pcb()
    image = add_traces(image)

    # Add components except one resistor (leave empty space)
    cv2.rectangle(image, (100, 200), (150, 220), (139, 69, 19), -1)  # One resistor

    # Capacitors
    cv2.rectangle(image, (200, 150), (250, 170), (200, 200, 200), -1)
    cv2.rectangle(image, (200, 250), (250, 270), (200, 200, 200), -1)

    # ICs
    cv2.rectangle(image, (300, 200), (340, 250), (30, 30, 30), -1)
    cv2.rectangle(image, (400, 100), (450, 150), (30, 30, 30), -1)

    # Show empty pads where component is missing
    pad_color = (100, 180, 220)
    cv2.circle(image, (120, 110), 3, pad_color, -1)
    cv2.circle(image, (140, 110), 3, pad_color, -1)

    return image


def create_corrosion():
    """Create PCB with corrosion/oxidation."""
    image = create_good_board()
    # Green oxidation on copper trace
    cv2.circle(image, (170, 135), 10, (50, 200, 100), -1)
    cv2.circle(image, (185, 140), 8, (60, 210, 110), -1)
    return image


def create_broken_trace():
    """Create PCB with broken trace."""
    image = create_base_pcb()
    image = add_components(image)

    # Add traces
    trace_color = (80, 150, 180)
    cv2.line(image, (120, 110), (170, 135), trace_color, 2)
    # Broken section
    cv2.line(image, (190, 145), (220, 160), trace_color, 2)
    cv2.line(image, (140, 110), (240, 160), trace_color, 2)

    return image


def create_misaligned_component():
    """Create PCB with misaligned component."""
    image = create_base_pcb()
    image = add_traces(image)

    # Normal components
    cv2.rectangle(image, (100, 100), (150, 120), (139, 69, 19), -1)
    cv2.rectangle(image, (200, 150), (250, 170), (200, 200, 200), -1)

    # Misaligned component (rotated and offset from pads)
    center = (125, 210)
    size = (50, 20)
    angle = 15  # 15 degree rotation
    box = cv2.boxPoints(((center[0], center[1]), size, angle))
    box = np.int32(box)
    cv2.fillPoly(image, [box], (139, 69, 19))

    return image


def create_contamination():
    """Create PCB with contamination."""
    image = create_good_board()
    # Flux residue (whitish/yellowish spots)
    cv2.circle(image, (300, 300), 15, (180, 190, 200), -1)
    cv2.circle(image, (330, 310), 10, (170, 180, 190), -1)
    return image


def create_excess_solder():
    """Create PCB with excess solder."""
    image = create_good_board()
    # Large solder blob
    cv2.circle(image, (220, 160), 12, (190, 190, 190), -1)
    return image


def main():
    """Generate all test samples."""
    output_dir = Path(__file__).parent / "defect_samples"
    output_dir.mkdir(exist_ok=True)

    samples = {
        "good_board.jpg": create_good_board(),
        "solder_bridge.jpg": create_solder_bridge(),
        "cold_joint.jpg": create_cold_joint(),
        "burnt_component.jpg": create_burnt_component(),
        "missing_component.jpg": create_missing_component(),
        "corrosion.jpg": create_corrosion(),
        "broken_trace.jpg": create_broken_trace(),
        "misaligned_component.jpg": create_misaligned_component(),
        "contamination.jpg": create_contamination(),
        "excess_solder.jpg": create_excess_solder(),
    }

    for filename, image in samples.items():
        filepath = output_dir / filename
        cv2.imwrite(str(filepath), image)
        print(f"Created: {filepath}")

    # Create README for the test data
    readme_path = output_dir / "README.md"
    with open(readme_path, "w") as f:
        f.write("# PCB Defect Test Samples\n\n")
        f.write("Synthetic PCB images for testing defect detection.\n\n")
        f.write("## Samples:\n\n")
        f.write("- **good_board.jpg**: Pristine PCB with no defects\n")
        f.write("- **solder_bridge.jpg**: Solder bridge connecting pads\n")
        f.write("- **cold_joint.jpg**: Cold solder joint (dull, cracked)\n")
        f.write("- **burnt_component.jpg**: Burnt resistor with discoloration\n")
        f.write("- **missing_component.jpg**: PCB with missing resistor\n")
        f.write("- **corrosion.jpg**: Green oxidation on copper\n")
        f.write("- **broken_trace.jpg**: Broken PCB trace\n")
        f.write("- **misaligned_component.jpg**: Component not aligned to pads\n")
        f.write("- **contamination.jpg**: Flux residue contamination\n")
        f.write("- **excess_solder.jpg**: Excessive solder on pad\n\n")
        f.write("## Usage:\n\n")
        f.write("```python\n")
        f.write("from vision.defect_detector import DefectDetector\n")
        f.write("import cv2\n\n")
        f.write("detector = DefectDetector()\n")
        f.write("image = cv2.imread('tests/data/defect_samples/solder_bridge.jpg')\n")
        f.write("defects = detector.detect_defects(image)\n")
        f.write("```\n")

    print(f"\nCreated README: {readme_path}")
    print(f"\nTotal samples created: {len(samples)}")


if __name__ == "__main__":
    main()
