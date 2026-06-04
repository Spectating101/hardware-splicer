import numpy as np
import os
from loguru import logger
from typing import Optional

try:
    import easyocr  # type: ignore
except Exception:
    easyocr = None

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    from paddleocr import PaddleOCR  # type: ignore
except Exception:
    PaddleOCR = None


class OCREngine:
    """Robust OCR Engine with optional PaddleOCR/EasyOCR/Tesseract backends."""
    
    def __init__(self, languages=None, preferred_backend: Optional[str] = None):
        self.languages = languages or ["en"]
        self.reader = None
        self.paddle_reader = None
        self.requested_backend = (preferred_backend or os.getenv("CIRCUIT_AI_OCR_BACKEND", "easyocr")).lower().strip()

        if PaddleOCR is not None and self.requested_backend in {"", "paddleocr", "paddle"}:
            self.backend = "paddleocr"
        elif easyocr is not None and self.requested_backend in {"", "easyocr", "easy"}:
            self.backend = "easyocr"
        else:
            self.backend = "tesseract" if pytesseract is not None else "disabled"
            if self.backend == "tesseract":
                logger.info("EasyOCR not installed; using pytesseract OCR fallback")
            else:
                logger.warning("easyocr/pytesseract not installed; OCR disabled")

    def read_text(self, image: np.ndarray) -> str:
        """
        Read text from an image crop.
        Args:
            image: Numpy array (RGB or Grayscale)
        Returns:
            Detected text string
        """
        if self.backend == "disabled":
            return ""
        try:
            self._ensure_backend_loaded()
            if self.paddle_reader is not None:
                return self._read_with_paddleocr(self._prepare_color_crop(image))

            image = self._prepare_crop(image)
            if self.reader is not None:
                # EasyOCR handles rotation/skew automatically better than Tesseract
                results = self.reader.readtext(image, detail=0)
                return " ".join(results)
            return self._read_with_tesseract(image)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    def _ensure_backend_loaded(self) -> None:
        if self.backend == "paddleocr" and self.paddle_reader is None:
            lang = self._paddle_lang(self.languages[0] if self.languages else "en")
            try:
                try:
                    self.paddle_reader = PaddleOCR(lang=lang, use_textline_orientation=True)
                except TypeError:
                    self.paddle_reader = PaddleOCR(lang=lang)
                logger.info("PaddleOCR initialized")
                return
            except Exception as e:
                logger.warning(f"PaddleOCR initialization failed: {e}. Falling back to EasyOCR/Tesseract.")
                self.backend = "easyocr" if easyocr is not None else "tesseract" if pytesseract is not None else "disabled"

        if self.backend == "easyocr" and self.reader is None and easyocr is not None:
            try:
                self.reader = easyocr.Reader(self.languages, gpu=True)
                logger.info("EasyOCR initialized (GPU=True)")
            except Exception as e:
                logger.warning(f"EasyOCR initialization failed: {e}. Falling back to CPU.")
                self.reader = easyocr.Reader(self.languages, gpu=False)

    def _read_with_tesseract(self, image: np.ndarray) -> str:
        attempts = []
        for psm in (6, 7, 11):
            attempts.append(
                pytesseract.image_to_string(
                    image,
                    config=(
                        f"--psm {psm} "
                        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_/+."
                    ),
                )
            )
        return max((text.strip() for text in attempts), key=len, default="")

    def _read_with_paddleocr(self, image: np.ndarray) -> str:
        try:
            result = self.paddle_reader.ocr(image, cls=True)
        except Exception:
            result = self.paddle_reader.ocr(image)
        candidates = []

        def visit(node) -> None:
            if isinstance(node, dict):
                for key in ("rec_texts", "text", "texts"):
                    value = node.get(key)
                    if isinstance(value, str):
                        candidates.append((value.strip(), 0.0))
                    elif isinstance(value, (list, tuple)):
                        for item in value:
                            if isinstance(item, str):
                                candidates.append((item.strip(), 0.0))
                for child in node.values():
                    if isinstance(child, (list, tuple, dict)):
                        visit(child)
                return
            if hasattr(node, "json"):
                try:
                    visit(node.json)
                    return
                except Exception:
                    pass
            if isinstance(node, tuple) and len(node) >= 1 and isinstance(node[0], str):
                confidence = 0.0
                if len(node) > 1 and isinstance(node[1], (int, float)):
                    confidence = float(node[1])
                candidates.append((node[0].strip(), confidence))
                return
            if isinstance(node, (list, tuple)):
                if (
                    len(node) >= 2
                    and isinstance(node[1], (list, tuple))
                    and len(node[1]) >= 1
                    and isinstance(node[1][0], str)
                ):
                    text = node[1][0].strip()
                    confidence = (
                        float(node[1][1])
                        if len(node[1]) > 1 and isinstance(node[1][1], (int, float))
                        else 0.0
                    )
                    candidates.append((text, confidence))
                    return
                for child in node:
                    visit(child)

        visit(result)
        return " ".join(text for text, _confidence in candidates if text)

    def _prepare_crop(self, image: np.ndarray) -> np.ndarray:
        crop = np.asarray(image)
        if crop.ndim == 3 and crop.shape[-1] == 3 and cv2 is not None:
            crop = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        if crop.dtype != np.uint8:
            crop = np.clip(crop, 0, 255).astype(np.uint8)
        if cv2 is None:
            return crop

        height, width = crop.shape[:2]
        if max(height, width) < 220:
            scale = max(2.0, 220.0 / max(height, width, 1))
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        crop = cv2.GaussianBlur(crop, (3, 3), 0)
        return cv2.adaptiveThreshold(
            crop,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )

    def _prepare_color_crop(self, image: np.ndarray) -> np.ndarray:
        crop = np.asarray(image)
        if crop.ndim == 2:
            if cv2 is not None:
                crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            else:
                crop = np.stack([crop, crop, crop], axis=-1)
        if crop.dtype != np.uint8:
            crop = np.clip(crop, 0, 255).astype(np.uint8)
        if cv2 is None:
            return crop

        height, width = crop.shape[:2]
        if max(height, width) < 220:
            scale = max(2.0, 220.0 / max(height, width, 1))
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return crop

    @staticmethod
    def _paddle_lang(language: str) -> str:
        normalized = (language or "en").lower()
        if normalized in {"en", "eng", "english"}:
            return "en"
        if normalized in {"ch", "cn", "zh", "zh-cn", "chinese"}:
            return "ch"
        return normalized
