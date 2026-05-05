import numpy as np
from src.vision import image_polisher


def test_polish_for_inference_accepts_grayscale_and_returns_float_rgb():
    raw = np.full((48, 72), 128, dtype=np.uint8)
    polished, metadata = image_polisher.polish_for_inference(raw)

    assert polished.shape == (48, 72, 3)
    assert polished.dtype == np.float32
    assert polished.min() >= 0.0
    assert polished.max() <= 1.0
    assert metadata["steps_applied"]
    assert metadata["output_shape"] == (48, 72, 3)


def test_polish_for_opencv_returns_bgr_uint8_when_possible():
    raw = np.random.randint(0, 255, (40, 50, 3), dtype=np.uint8)
    polished, metadata = image_polisher.polish_for_opencv(raw)

    assert polished.shape == (40, 50, 3)
    assert polished.dtype == np.uint8
    assert metadata["opencv_available"] is True
    assert "steps_applied" in metadata

