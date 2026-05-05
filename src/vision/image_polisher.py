"""Image polishing utilities for PCB analysis quality.

The goal is to reduce lighting/contrast/texture noise before
component and classical CV stages while keeping changes deterministic.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    cv2 = None


def _to_uint8_rgb(image: np.ndarray) -> np.ndarray:
    """Convert incoming arrays to uint8 RGB without changing layout assumptions."""
    img = np.asarray(image)
    if img.ndim == 2:
        img = np.stack([img, img, img], axis=-1)
    elif img.ndim == 3:
        if img.shape[-1] == 4:
            img = img[..., :3]
        elif img.shape[-1] != 3:
            raise ValueError(f"Unsupported image shape for preprocessing: {img.shape}")
    else:
        raise ValueError(f"Unsupported image shape for preprocessing: {img.shape}")

    if img.dtype == np.uint8:
        return img.copy()

    img = img.astype(np.float32, copy=False)
    if img.max(initial=0.0) <= 1.0:
        img = img * 255.0
    return np.clip(img, 0, 255).astype(np.uint8)


def _to_float_rgb(image_u8: np.ndarray) -> np.ndarray:
    """Convert a uint8 RGB image to float32 RGB in [0, 1]."""
    return image_u8.astype(np.float32) / 255.0


def _apply_channel_normalization(image_bgr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Apply basic gray-world white-balance in BGR space."""
    means = np.array([np.mean(image_bgr[:, :, c]) for c in range(3)], dtype=np.float32)
    if np.any(~np.isfinite(means)) or means.max() <= 0.0:
        return image_bgr, {"white_balance": "skipped"}

    target = float(means.mean())
    gains = np.where(means > 0, target / np.clip(means, 1e-6, None), 1.0)
    balanced = image_bgr.astype(np.float32) * gains[None, None, :]
    return np.clip(balanced, 0, 255).astype(np.uint8), {
        "white_balance": "applied",
        "channel_means_before": [float(v) for v in means],
        "channel_gains": [float(v) for v in gains],
    }


def _apply_clahe(image_bgr: np.ndarray, clip_limit: float = 2.2, tile_grid: Tuple[int, int] = (8, 8)) -> Tuple[np.ndarray, Dict[str, Any]]:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    enhanced_l = clahe.apply(l_channel)
    merged = cv2.merge((enhanced_l, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR), {
        "clahe": {
            "clip_limit": float(clip_limit),
            "tile_grid": tuple(int(v) for v in tile_grid),
        }
    }


def _apply_denoise(image_bgr: np.ndarray, h: float = 8.0, h_color: float = 10.0) -> Tuple[np.ndarray, Dict[str, Any]]:
    denoised = cv2.fastNlMeansDenoisingColored(image_bgr, None, h, h_color, 7, 21)
    return denoised, {"denoise": {"h": float(h), "h_color": float(h_color)}}


def _apply_sharpen(image_bgr: np.ndarray, amount: float = 0.4, sigma: float = 1.0) -> Tuple[np.ndarray, Dict[str, Any]]:
    blur = cv2.GaussianBlur(image_bgr, (0, 0), sigmaX=sigma, sigmaY=sigma)
    sharpened = cv2.addWeighted(image_bgr, 1.0 + amount, blur, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8), {"sharpen": {"amount": float(amount), "sigma": float(sigma)}}


def _apply_gamma(image_bgr: np.ndarray, gamma: float = 1.08) -> Tuple[np.ndarray, Dict[str, Any]]:
    if gamma <= 0:
        gamma = 1.0
    inv_gamma = 1.0 / gamma
    lut = np.array([(255.0 * ((i / 255.0) ** inv_gamma)) for i in range(256)], dtype=np.uint8)
    return cv2.LUT(image_bgr, lut), {"gamma": float(gamma)}


def polish_for_inference(
    image: np.ndarray,
    *,
    enable_white_balance: bool = True,
    enable_clahe: bool = True,
    enable_denoise: bool = True,
    enable_sharpen: bool = True,
    enable_gamma: bool = True,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Return a quality-polished RGB image for model input and metadata.

    Steps are intentionally conservative and deterministic. If OpenCV is unavailable,
    the image is passed through normalization only.
    """
    base = _to_uint8_rgb(image)
    metadata: Dict[str, Any] = {"steps_applied": []}

    if cv2 is None:
        metadata["opencv_available"] = False
        return _to_float_rgb(base), {"opencv_available": False, "steps_applied": []}

    metadata["opencv_available"] = True
    # Work in BGR for stable OpenCV operations.
    bgr = cv2.cvtColor(base, cv2.COLOR_RGB2BGR)

    if enable_white_balance:
        bgr, wb_meta = _apply_channel_normalization(bgr)
        metadata["steps_applied"].append("white_balance")
        metadata["white_balance"] = wb_meta

    if enable_clahe:
        bgr, clahe_meta = _apply_clahe(bgr)
        metadata["steps_applied"].append("clahe")
        metadata["clahe"] = clahe_meta

    h, w = bgr.shape[:2]
    # Denoising is expensive on large images; only enable for modest frames.
    if enable_denoise and h * w <= 4_000_000:
        bgr, denoise_meta = _apply_denoise(bgr)
        metadata["steps_applied"].append("denoise")
        metadata["denoise"] = denoise_meta

    if enable_sharpen:
        bgr, sharp_meta = _apply_sharpen(bgr)
        metadata["steps_applied"].append("sharpen")
        metadata["sharpen"] = sharp_meta

    if enable_gamma:
        bgr, gamma_meta = _apply_gamma(bgr)
        metadata["steps_applied"].append("gamma")
        metadata["gamma"] = gamma_meta

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return _to_float_rgb(rgb), {
        **metadata,
        "input_shape": tuple(int(v) for v in base.shape),
        "output_shape": tuple(int(v) for v in rgb.shape),
    }


def polish_for_opencv(
    image: np.ndarray,
    *,
    input_is_bgr: bool = False,
    enable_white_balance: bool = True,
    enable_clahe: bool = True,
    enable_denoise: bool = True,
    enable_sharpen: bool = True,
    enable_gamma: bool = True,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Return a polished BGR image for classical CV passes and metadata.
    """
    base = _to_uint8_rgb(image)
    if input_is_bgr:
        base_bgr = base
    else:
        base_bgr = cv2.cvtColor(base, cv2.COLOR_RGB2BGR) if cv2 is not None else base

    if cv2 is None:
        return base_bgr, {"opencv_available": False}

    metadata: Dict[str, Any] = {"steps_applied": [], "opencv_available": True}
    bgr = base_bgr

    if enable_white_balance:
        bgr, wb_meta = _apply_channel_normalization(bgr)
        metadata["steps_applied"].append("white_balance")
        metadata["white_balance"] = wb_meta

    if enable_clahe:
        bgr, clahe_meta = _apply_clahe(bgr)
        metadata["steps_applied"].append("clahe")
        metadata["clahe"] = clahe_meta

    h, w = bgr.shape[:2]
    if enable_denoise and h * w <= 4_000_000:
        bgr, denoise_meta = _apply_denoise(bgr)
        metadata["steps_applied"].append("denoise")
        metadata["denoise"] = denoise_meta

    if enable_sharpen:
        bgr, sharp_meta = _apply_sharpen(bgr)
        metadata["steps_applied"].append("sharpen")
        metadata["sharpen"] = sharp_meta

    if enable_gamma:
        bgr, gamma_meta = _apply_gamma(bgr)
        metadata["steps_applied"].append("gamma")
        metadata["gamma"] = gamma_meta

    return bgr, {
        **metadata,
        "input_shape": tuple(int(v) for v in base_bgr.shape),
        "output_shape": tuple(int(v) for v in bgr.shape),
    }
