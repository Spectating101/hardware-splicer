import numpy as np

import src.vision.ocr_engine as ocr_module
from src.vision.ocr_engine import OCREngine


class FakePaddleOCR:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def ocr(self, image, cls=True):
        assert image.dtype == np.uint8
        assert cls is True
        return [
            [
                [[[0, 0], [10, 0], [10, 10], [0, 10]], ("ATMEGA328P", 0.93)],
                [[[12, 0], [20, 0], [20, 10], [12, 10]], ("VIN", 0.88)],
            ]
        ]


def test_paddleocr_backend_is_optional_and_parses_text(monkeypatch) -> None:
    monkeypatch.setattr(ocr_module, "PaddleOCR", FakePaddleOCR)

    engine = OCREngine(preferred_backend="paddleocr")
    text = engine.read_text(np.zeros((24, 80, 3), dtype=np.uint8))

    assert engine.backend == "paddleocr"
    assert text == "ATMEGA328P VIN"


def test_paddle_lang_normalizes_common_names() -> None:
    assert OCREngine._paddle_lang("eng") == "en"
    assert OCREngine._paddle_lang("zh-cn") == "ch"
    assert OCREngine._paddle_lang("japan") == "japan"
