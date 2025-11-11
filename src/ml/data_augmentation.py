"""
Advanced Data Augmentation for PCB Training

Realistic augmentations specific to PCB analysis:
- Lighting variations (overexposure, underexposure, shadows)
- Focus blur (microscope out of focus)
- Angle variations (non-perpendicular viewing)
- Reflections on solder/components
- Dust and scratches
- Color temperature variations
"""

import cv2
import numpy as np
from typing import Tuple, List
import random
from dataclasses import dataclass


@dataclass
class AugmentationConfig:
    """Configuration for augmentation pipeline."""
    lighting_prob: float = 0.5
    blur_prob: float = 0.3
    angle_prob: float = 0.4
    reflection_prob: float = 0.3
    noise_prob: float = 0.2
    color_temp_prob: float = 0.3


class PCBAugmentor:
    """Advanced augmentation for PCB images."""

    def __init__(self, config: AugmentationConfig = None):
        """Initialize augmentor."""
        self.config = config or AugmentationConfig()

    def augment(self, image: np.ndarray, boxes: List[Tuple[int, int, int, int]],
                labels: List[int]) -> Tuple[np.ndarray, List[Tuple[int, int, int, int]], List[int]]:
        """
        Apply augmentation pipeline.

        Args:
            image: Input image
            boxes: Bounding boxes [(x1, y1, x2, y2), ...]
            labels: Class labels

        Returns:
            (augmented_image, augmented_boxes, labels)
        """
        aug_image = image.copy()

        # Lighting variations
        if random.random() < self.config.lighting_prob:
            aug_image = self._augment_lighting(aug_image)

        # Blur (out of focus)
        if random.random() < self.config.blur_prob:
            aug_image = self._augment_blur(aug_image)

        # Angle variation (perspective transform)
        if random.random() < self.config.angle_prob:
            aug_image, boxes = self._augment_angle(aug_image, boxes)

        # Reflections
        if random.random() < self.config.reflection_prob:
            aug_image = self._augment_reflections(aug_image)

        # Noise
        if random.random() < self.config.noise_prob:
            aug_image = self._augment_noise(aug_image)

        # Color temperature
        if random.random() < self.config.color_temp_prob:
            aug_image = self._augment_color_temperature(aug_image)

        return aug_image, boxes, labels

    def _augment_lighting(self, image: np.ndarray) -> np.ndarray:
        """
        Simulate lighting variations.

        Types:
        - Overexposure (too bright)
        - Underexposure (too dark)
        - Uneven lighting (shadow on one side)
        """
        aug_type = random.choice(['overexposed', 'underexposed', 'uneven'])

        if aug_type == 'overexposed':
            # Increase brightness
            factor = random.uniform(1.2, 1.8)
            return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        elif aug_type == 'underexposed':
            # Decrease brightness
            factor = random.uniform(0.3, 0.7)
            return np.clip(image.astype(np.float32) * factor, 0, 255).astype(np.uint8)

        elif aug_type == 'uneven':
            # Create gradient mask
            h, w = image.shape[:2]
            gradient = np.linspace(0.5, 1.5, w)
            gradient = np.tile(gradient, (h, 1))

            if len(image.shape) == 3:
                gradient = gradient[:, :, np.newaxis]

            return np.clip(image.astype(np.float32) * gradient, 0, 255).astype(np.uint8)

    def _augment_blur(self, image: np.ndarray) -> np.ndarray:
        """
        Simulate out-of-focus blur.

        Types:
        - Gaussian blur (entire image out of focus)
        - Motion blur (camera shake)
        """
        blur_type = random.choice(['gaussian', 'motion'])

        if blur_type == 'gaussian':
            kernel_size = random.choice([3, 5, 7])
            return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)

        elif blur_type == 'motion':
            # Create motion blur kernel
            kernel_size = random.randint(5, 15)
            kernel = np.zeros((kernel_size, kernel_size))
            kernel[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
            kernel = kernel / kernel_size

            # Apply motion blur
            return cv2.filter2D(image, -1, kernel)

    def _augment_angle(self, image: np.ndarray, boxes: List[Tuple[int, int, int, int]]) -> Tuple[np.ndarray, List]:
        """
        Simulate non-perpendicular viewing angle.

        Uses perspective transform to simulate 3D rotation.
        """
        h, w = image.shape[:2]

        # Random perspective transform
        # Source points (image corners)
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

        # Destination points (with random shift)
        shift = w * random.uniform(0.05, 0.15)
        dst_pts = np.float32([
            [random.uniform(0, shift), random.uniform(0, shift)],
            [w - random.uniform(0, shift), random.uniform(0, shift)],
            [w - random.uniform(0, shift), h - random.uniform(0, shift)],
            [random.uniform(0, shift), h - random.uniform(0, shift)]
        ])

        # Get transform matrix
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)

        # Apply to image
        aug_image = cv2.warpPerspective(image, M, (w, h))

        # Transform bounding boxes
        aug_boxes = []
        for box in boxes:
            x1, y1, x2, y2 = box

            # Transform corners
            corners = np.float32([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
            corners = corners.reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(corners, M)

            # Get new bounding box
            x_coords = transformed[:, 0, 0]
            y_coords = transformed[:, 0, 1]

            new_x1 = int(np.min(x_coords))
            new_y1 = int(np.min(y_coords))
            new_x2 = int(np.max(x_coords))
            new_y2 = int(np.max(y_coords))

            # Clip to image bounds
            new_x1 = max(0, min(w, new_x1))
            new_y1 = max(0, min(h, new_y1))
            new_x2 = max(0, min(w, new_x2))
            new_y2 = max(0, min(h, new_y2))

            if new_x2 > new_x1 and new_y2 > new_y1:
                aug_boxes.append((new_x1, new_y1, new_x2, new_y2))

        return aug_image, aug_boxes

    def _augment_reflections(self, image: np.ndarray) -> np.ndarray:
        """
        Simulate reflections on shiny components.

        Adds bright spots to simulate light reflecting off solder/ICs.
        """
        aug_image = image.copy()
        h, w = image.shape[:2]

        # Add random bright spots
        num_reflections = random.randint(2, 8)

        for _ in range(num_reflections):
            # Random position
            x = random.randint(0, w - 1)
            y = random.randint(0, h - 1)

            # Random size
            radius = random.randint(5, 30)

            # Create circular reflection (Gaussian)
            Y, X = np.ogrid[:h, :w]
            dist_from_center = np.sqrt((X - x)**2 + (Y - y)**2)

            mask = np.exp(-(dist_from_center**2) / (2 * (radius/2)**2))
            mask = mask / mask.max()

            # Add bright spot
            if len(image.shape) == 3:
                mask = mask[:, :, np.newaxis]

            brightness = random.uniform(100, 200)
            aug_image = np.clip(aug_image.astype(np.float32) + mask * brightness, 0, 255).astype(np.uint8)

        return aug_image

    def _augment_noise(self, image: np.ndarray) -> np.ndarray:
        """
        Add noise to simulate:
        - Sensor noise (high ISO)
        - Electronic interference
        """
        noise_type = random.choice(['gaussian', 'salt_pepper'])

        if noise_type == 'gaussian':
            # Gaussian noise
            mean = 0
            sigma = random.uniform(5, 25)
            noise = np.random.normal(mean, sigma, image.shape).astype(np.float32)

            return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

        elif noise_type == 'salt_pepper':
            # Salt and pepper noise
            prob = random.uniform(0.001, 0.01)
            aug_image = image.copy()

            # Salt
            salt_mask = np.random.random(image.shape[:2]) < (prob / 2)
            aug_image[salt_mask] = 255

            # Pepper
            pepper_mask = np.random.random(image.shape[:2]) < (prob / 2)
            aug_image[pepper_mask] = 0

            return aug_image

    def _augment_color_temperature(self, image: np.ndarray) -> np.ndarray:
        """
        Simulate different color temperatures.

        - Warm (yellowish) - incandescent light
        - Cool (bluish) - LED/fluorescent light
        """
        if len(image.shape) != 3:
            return image

        temp_type = random.choice(['warm', 'cool', 'neutral'])

        aug_image = image.copy().astype(np.float32)

        if temp_type == 'warm':
            # Increase red/yellow
            aug_image[:, :, 2] *= random.uniform(1.1, 1.3)  # Red
            aug_image[:, :, 1] *= random.uniform(1.05, 1.15)  # Green

        elif temp_type == 'cool':
            # Increase blue
            aug_image[:, :, 0] *= random.uniform(1.1, 1.3)  # Blue
            aug_image[:, :, 1] *= random.uniform(0.95, 1.05)  # Green

        return np.clip(aug_image, 0, 255).astype(np.uint8)


# Global augmentor
pcb_augmentor = PCBAugmentor()
