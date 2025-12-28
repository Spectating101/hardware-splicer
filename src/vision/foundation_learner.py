"""
Foundation Model-Based Few-Shot Component Learner

Learns new PCB component types from 3-5 examples using:
- CLIP-ViT embeddings (vision-language foundation model)
- DINOv2 embeddings (self-supervised vision foundation model)
- Cosine similarity for classification
- Prototype storage for incremental learning

Enables Dum-E to adapt to new components without retraining.

Based on: https://www.mdpi.com/2313-433x/11/11/415

Author: Dum-E Vision System
Version: 1.0.0
"""

import numpy as np
import cv2
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
import pickle

logger = logging.getLogger(__name__)


@dataclass
class ComponentPrototype:
    """Learned component prototype from few-shot examples."""
    component_name: str
    embedding: np.ndarray  # Mean embedding from examples
    example_embeddings: List[np.ndarray] = field(default_factory=list)
    example_count: int = 0
    confidence_threshold: float = 0.75  # Min similarity to classify as this component

    def to_dict(self) -> Dict:
        """Export to dictionary (for JSON serialization)."""
        return {
            "component_name": self.component_name,
            "embedding": self.embedding.tolist(),
            "example_embeddings": [e.tolist() for e in self.example_embeddings],
            "example_count": self.example_count,
            "confidence_threshold": self.confidence_threshold
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ComponentPrototype':
        """Load from dictionary."""
        return cls(
            component_name=data["component_name"],
            embedding=np.array(data["embedding"]),
            example_embeddings=[np.array(e) for e in data.get("example_embeddings", [])],
            example_count=data.get("example_count", 0),
            confidence_threshold=data.get("confidence_threshold", 0.75)
        )


class FoundationLearner:
    """
    Few-shot component learner using foundation models.

    Supports two embedding methods:
    1. CLIP-ViT: Vision-language model (requires transformers library)
    2. DINOv2: Self-supervised vision model (requires transformers library)

    Can learn new component types from as few as 3-5 examples.
    """

    def __init__(
        self,
        embedding_model: str = "clip",
        knowledge_base_path: Optional[Path] = None
    ):
        """
        Initialize foundation learner.

        Args:
            embedding_model: "clip" or "dinov2"
            knowledge_base_path: Path to save/load learned prototypes
        """
        self.embedding_model_name = embedding_model
        self.knowledge_base_path = knowledge_base_path or Path("component_knowledge_base.pkl")

        # Model and preprocessor (lazy loading)
        self.model = None
        self.processor = None

        # Learned prototypes
        self.prototypes: Dict[str, ComponentPrototype] = {}

        # Load existing knowledge base
        self._load_knowledge_base()

        logger.info(f"FoundationLearner initialized (model: {embedding_model})")

    def _load_model(self):
        """Lazy load embedding model."""
        if self.model is not None:
            return

        try:
            if self.embedding_model_name == "clip":
                from transformers import CLIPProcessor, CLIPModel

                logger.info("Loading CLIP-ViT model...")
                self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
                self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
                logger.info("✓ CLIP model loaded")

            elif self.embedding_model_name == "dinov2":
                from transformers import AutoImageProcessor, AutoModel

                logger.info("Loading DINOv2 model...")
                self.model = AutoModel.from_pretrained("facebook/dinov2-base")
                self.processor = AutoImageProcessor.from_pretrained("facebook/dinov2-base")
                logger.info("✓ DINOv2 model loaded")

            else:
                raise ValueError(f"Unknown embedding model: {self.embedding_model_name}")

        except ImportError:
            logger.error("transformers library required for foundation models")
            logger.error("Install: pip install transformers torch")
            raise

    def learn_component(
        self,
        component_name: str,
        example_images: List[np.ndarray],
        confidence_threshold: float = 0.75
    ) -> ComponentPrototype:
        """
        Learn new component type from examples.

        Args:
            component_name: Name of the component (e.g., "ESP32", "ATmega328")
            example_images: List of example images (3-5 recommended)
            confidence_threshold: Minimum similarity for classification

        Returns:
            ComponentPrototype with learned embeddings
        """
        if len(example_images) < 3:
            logger.warning(f"Only {len(example_images)} examples provided. 3-5 recommended for robust learning.")

        logger.info(f"Learning component '{component_name}' from {len(example_images)} examples...")

        # Extract embeddings from all examples
        embeddings = []
        for i, image in enumerate(example_images, 1):
            embedding = self._extract_embedding(image)
            embeddings.append(embedding)
            logger.debug(f"  Extracted embedding {i}/{len(example_images)}")

        # Compute mean embedding (prototype)
        mean_embedding = np.mean(embeddings, axis=0)

        # Create prototype
        prototype = ComponentPrototype(
            component_name=component_name,
            embedding=mean_embedding,
            example_embeddings=embeddings,
            example_count=len(embeddings),
            confidence_threshold=confidence_threshold
        )

        # Store in knowledge base
        self.prototypes[component_name] = prototype
        self._save_knowledge_base()

        logger.info(f"✓ Learned component '{component_name}' (threshold: {confidence_threshold})")

        return prototype

    def classify_component(
        self,
        image: np.ndarray,
        top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Classify component in image using learned prototypes.

        Args:
            image: Input image crop containing component
            top_k: Return top-k matches

        Returns:
            [(component_name, similarity_score), ...] sorted by score
        """
        if len(self.prototypes) == 0:
            logger.warning("No prototypes learned yet. Returning empty results.")
            return []

        # Extract embedding from query image
        query_embedding = self._extract_embedding(image)

        # Compute similarity to all prototypes
        similarities = []

        for component_name, prototype in self.prototypes.items():
            similarity = self._cosine_similarity(query_embedding, prototype.embedding)
            similarities.append((component_name, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top-k
        return similarities[:top_k]

    def recognize_component(
        self,
        image: np.ndarray
    ) -> Optional[Tuple[str, float]]:
        """
        Recognize component (single best match above threshold).

        Args:
            image: Input image crop

        Returns:
            (component_name, confidence) or None if no match
        """
        results = self.classify_component(image, top_k=1)

        if not results:
            return None

        component_name, similarity = results[0]
        prototype = self.prototypes[component_name]

        # Check threshold
        if similarity >= prototype.confidence_threshold:
            return (component_name, similarity)
        else:
            return None

    def _extract_embedding(self, image: np.ndarray) -> np.ndarray:
        """
        Extract embedding vector from image.

        Args:
            image: Input image (BGR format from OpenCV)

        Returns:
            Embedding vector (normalized)
        """
        self._load_model()

        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Preprocess
        if self.embedding_model_name == "clip":
            inputs = self.processor(images=image_rgb, return_tensors="pt")
            outputs = self.model.get_image_features(**inputs)
            embedding = outputs[0].detach().numpy()

        elif self.embedding_model_name == "dinov2":
            inputs = self.processor(images=image_rgb, return_tensors="pt")
            outputs = self.model(**inputs)
            # Use [CLS] token embedding
            embedding = outputs.last_hidden_state[:, 0, :][0].detach().numpy()

        else:
            raise ValueError(f"Unknown model: {self.embedding_model_name}")

        # Normalize
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _save_knowledge_base(self):
        """Save learned prototypes to disk."""
        try:
            data = {
                "embedding_model": self.embedding_model_name,
                "prototypes": {
                    name: proto.to_dict()
                    for name, proto in self.prototypes.items()
                }
            }

            with open(self.knowledge_base_path, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"Saved knowledge base: {self.knowledge_base_path} ({len(self.prototypes)} prototypes)")

        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")

    def _load_knowledge_base(self):
        """Load learned prototypes from disk."""
        if not self.knowledge_base_path.exists():
            logger.info("No existing knowledge base found, starting fresh")
            return

        try:
            with open(self.knowledge_base_path, 'rb') as f:
                data = pickle.load(f)

            # Verify model compatibility
            if data.get("embedding_model") != self.embedding_model_name:
                logger.warning(f"Knowledge base uses different model ({data.get('embedding_model')}), "
                             f"but current model is {self.embedding_model_name}. Prototypes may not be compatible.")

            # Load prototypes
            self.prototypes = {
                name: ComponentPrototype.from_dict(proto_dict)
                for name, proto_dict in data.get("prototypes", {}).items()
            }

            logger.info(f"Loaded {len(self.prototypes)} prototype(s) from knowledge base")

        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            self.prototypes = {}

    def get_learned_components(self) -> List[str]:
        """Get list of learned component names."""
        return list(self.prototypes.keys())

    def remove_component(self, component_name: str):
        """Remove a learned component."""
        if component_name in self.prototypes:
            del self.prototypes[component_name]
            self._save_knowledge_base()
            logger.info(f"Removed component '{component_name}' from knowledge base")
        else:
            logger.warning(f"Component '{component_name}' not found in knowledge base")

    def generate_report(self) -> str:
        """Generate knowledge base report."""
        lines = []

        lines.append("=" * 70)
        lines.append("COMPONENT KNOWLEDGE BASE")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Embedding Model: {self.embedding_model_name}")
        lines.append(f"Total Components Learned: {len(self.prototypes)}")
        lines.append("")

        if not self.prototypes:
            lines.append("No components learned yet.")
            lines.append("")
            lines.append("Use learn_component() to teach new components from 3-5 examples.")
        else:
            lines.append("Learned Components:")
            lines.append("")

            for component_name, prototype in self.prototypes.items():
                lines.append(f"  - {component_name}")
                lines.append(f"      Examples: {prototype.example_count}")
                lines.append(f"      Threshold: {prototype.confidence_threshold:.2f}")
                lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("Foundation Model Few-Shot Learner")
    print("==================================")
    print()
    print("This module learns new PCB components from 3-5 examples.")
    print()
    print("Requirements:")
    print("  pip install transformers torch")
    print()
    print("Example:")
    print("  learner = FoundationLearner(embedding_model='clip')")
    print("  learner.learn_component('ESP32', [img1, img2, img3, img4, img5])")
    print("  result = learner.recognize_component(unknown_component_image)")
    print("  if result:")
    print("      print(f'Recognized: {result[0]} (confidence: {result[1]:.2f})')")
