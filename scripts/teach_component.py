"""
Interactive Component Teaching CLI

Teaches Dum-E new PCB component types from example images.

Usage:
    python teach_component.py --name "ESP32" --examples esp32_*.jpg
    python teach_component.py --name "ATmega328" --examples atmega328_1.jpg atmega328_2.jpg atmega328_3.jpg

Author: Dum-E Vision System
Version: 1.0.0
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
import logging
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vision.foundation_learner import FoundationLearner


def load_images(image_paths: list[Path]) -> list[np.ndarray]:
    """Load images from file paths."""
    images = []

    for path in image_paths:
        if not path.exists():
            logging.warning(f"Image not found: {path}")
            continue

        image = cv2.imread(str(path))

        if image is None:
            logging.warning(f"Failed to load image: {path}")
            continue

        images.append(image)
        logging.info(f"✓ Loaded: {path.name} ({image.shape})")

    return images


def interactive_teaching_session(learner: FoundationLearner):
    """Interactive session for teaching multiple components."""
    print("\n" + "=" * 70)
    print("INTERACTIVE COMPONENT TEACHING SESSION")
    print("=" * 70)
    print()

    while True:
        print("Options:")
        print("  1. Teach new component")
        print("  2. List learned components")
        print("  3. Test recognition")
        print("  4. Remove component")
        print("  5. Show knowledge base report")
        print("  6. Exit")
        print()

        choice = input("Select option (1-6): ").strip()

        if choice == "1":
            teach_new_component(learner)

        elif choice == "2":
            list_components(learner)

        elif choice == "3":
            test_recognition(learner)

        elif choice == "4":
            remove_component(learner)

        elif choice == "5":
            show_report(learner)

        elif choice == "6":
            print("\nExiting interactive session.")
            break

        else:
            print("Invalid choice. Please select 1-6.")

        print()


def teach_new_component(learner: FoundationLearner):
    """Teach a new component."""
    print("\n--- Teach New Component ---")

    component_name = input("Component name: ").strip()

    if not component_name:
        print("Error: Component name cannot be empty.")
        return

    # Check if already exists
    if component_name in learner.get_learned_components():
        overwrite = input(f"Component '{component_name}' already exists. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Cancelled.")
            return

    # Get example images
    print("\nEnter image paths (one per line, empty line to finish):")
    image_paths = []

    while True:
        path_str = input("  Image path: ").strip()

        if not path_str:
            break

        path = Path(path_str)
        image_paths.append(path)

    if len(image_paths) < 3:
        print(f"\nWarning: Only {len(image_paths)} examples provided.")
        print("Recommendation: Provide 3-5 examples for robust learning.")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Cancelled.")
            return

    # Load images
    print(f"\nLoading {len(image_paths)} image(s)...")
    images = load_images(image_paths)

    if len(images) == 0:
        print("Error: No valid images loaded.")
        return

    # Confidence threshold
    threshold_str = input(f"Confidence threshold (0.0-1.0, default 0.75): ").strip()
    threshold = float(threshold_str) if threshold_str else 0.75

    # Learn component
    print(f"\nTeaching component '{component_name}' from {len(images)} example(s)...")

    try:
        prototype = learner.learn_component(component_name, images, threshold)
        print(f"\n✓ Successfully learned '{component_name}'!")
        print(f"  Examples: {prototype.example_count}")
        print(f"  Threshold: {prototype.confidence_threshold}")

    except Exception as e:
        print(f"\n✗ Failed to learn component: {e}")


def list_components(learner: FoundationLearner):
    """List all learned components."""
    print("\n--- Learned Components ---")

    components = learner.get_learned_components()

    if not components:
        print("No components learned yet.")
    else:
        for i, component in enumerate(components, 1):
            prototype = learner.prototypes[component]
            print(f"{i}. {component} ({prototype.example_count} examples, threshold: {prototype.confidence_threshold})")


def test_recognition(learner: FoundationLearner):
    """Test component recognition on an image."""
    print("\n--- Test Recognition ---")

    if len(learner.get_learned_components()) == 0:
        print("No components learned yet. Teach some components first.")
        return

    image_path_str = input("Image path to test: ").strip()

    if not image_path_str:
        print("Cancelled.")
        return

    image_path = Path(image_path_str)

    if not image_path.exists():
        print(f"Error: Image not found: {image_path}")
        return

    # Load image
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Error: Failed to load image: {image_path}")
        return

    print(f"\nAnalyzing image: {image_path.name}...")

    # Recognize
    try:
        result = learner.recognize_component(image)

        if result:
            component_name, confidence = result
            print(f"\n✓ Recognized: {component_name}")
            print(f"  Confidence: {confidence:.2f}")
        else:
            print("\n✗ No matching component found (below threshold)")

        # Show top-3 matches
        print("\nTop-3 matches:")
        top_matches = learner.classify_component(image, top_k=3)

        for i, (name, score) in enumerate(top_matches, 1):
            print(f"  {i}. {name}: {score:.2f}")

    except Exception as e:
        print(f"\n✗ Recognition failed: {e}")


def remove_component(learner: FoundationLearner):
    """Remove a learned component."""
    print("\n--- Remove Component ---")

    components = learner.get_learned_components()

    if not components:
        print("No components to remove.")
        return

    # List components
    for i, component in enumerate(components, 1):
        print(f"{i}. {component}")

    print()
    choice = input("Enter number to remove (or 'cancel'): ").strip()

    if choice.lower() == 'cancel':
        print("Cancelled.")
        return

    try:
        index = int(choice) - 1

        if 0 <= index < len(components):
            component_name = components[index]
            confirm = input(f"Remove '{component_name}'? (y/n): ").strip().lower()

            if confirm == 'y':
                learner.remove_component(component_name)
                print(f"✓ Removed '{component_name}'")
            else:
                print("Cancelled.")
        else:
            print("Invalid selection.")

    except ValueError:
        print("Invalid input.")


def show_report(learner: FoundationLearner):
    """Show knowledge base report."""
    print()
    print(learner.generate_report())


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Teach Dum-E new PCB component types from examples"
    )

    parser.add_argument(
        "--name",
        type=str,
        help="Component name (e.g., 'ESP32', 'ATmega328')"
    )

    parser.add_argument(
        "--examples",
        nargs="+",
        help="Example image paths (3-5 recommended)"
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Confidence threshold for recognition (default: 0.75)"
    )

    parser.add_argument(
        "--model",
        choices=["clip", "dinov2"],
        default="clip",
        help="Embedding model to use (default: clip)"
    )

    parser.add_argument(
        "--knowledge-base",
        type=Path,
        default=Path("component_knowledge_base.pkl"),
        help="Knowledge base file path"
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive teaching session"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    # Initialize learner
    print(f"Initializing foundation learner (model: {args.model})...")

    try:
        learner = FoundationLearner(
            embedding_model=args.model,
            knowledge_base_path=args.knowledge_base
        )
    except Exception as e:
        print(f"Error initializing learner: {e}")
        print("\nMake sure you have installed the required dependencies:")
        print("  pip install transformers torch")
        return 1

    # Interactive mode
    if args.interactive:
        interactive_teaching_session(learner)
        return 0

    # Batch mode
    if not args.name or not args.examples:
        print("Error: --name and --examples required for batch mode")
        print("Use --interactive for interactive teaching session")
        parser.print_help()
        return 1

    # Load example images
    example_paths = [Path(p) for p in args.examples]
    print(f"\nLoading {len(example_paths)} example image(s)...")
    images = load_images(example_paths)

    if len(images) == 0:
        print("Error: No valid images loaded")
        return 1

    # Teach component
    print(f"\nTeaching component '{args.name}' from {len(images)} example(s)...")

    try:
        prototype = learner.learn_component(args.name, images, args.threshold)

        print(f"\n✓ Successfully learned '{args.name}'!")
        print(f"  Examples: {prototype.example_count}")
        print(f"  Threshold: {prototype.confidence_threshold}")
        print(f"  Knowledge base: {args.knowledge_base}")

        return 0

    except Exception as e:
        print(f"\n✗ Failed to learn component: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
