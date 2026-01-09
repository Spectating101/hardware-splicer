import numpy as np
from loguru import logger
from typing import Optional

try:
    import easyocr  # type: ignore
except Exception:
    easyocr = None


class OCREngine:
    """Robust OCR Engine using EasyOCR (Deep Learning)."""
    
    def __init__(self, languages=['en']):
        if easyocr is None:
            self.reader = None
            logger.warning("easyocr not installed; OCR disabled")
            return
        try:
            # Initialize reader (will download model on first run)
            self.reader = easyocr.Reader(languages, gpu=True)
            logger.info("EasyOCR initialized (GPU=True)")
        except Exception as e:
            logger.warning(f"EasyOCR initialization failed: {e}. Falling back to CPU.")
            self.reader = easyocr.Reader(languages, gpu=False)

    def read_text(self, image: np.ndarray) -> str:
        """
        Read text from an image crop.
        Args:
            image: Numpy array (RGB or Grayscale)
        Returns:
            Detected text string
        """
        if self.reader is None:
            return ""
        try:
            # EasyOCR handles rotation/skew automatically better than Tesseract
            results = self.reader.readtext(image, detail=0)
            return " ".join(results)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""
