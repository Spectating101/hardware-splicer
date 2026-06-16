from __future__ import annotations

import pytest

from hardware_splicer.integrations.qwen_model_policy import (
    is_blocked_chat_model,
    is_qwen_free_quota_exhausted,
    qwen_text_model_candidates,
    qwen_vision_model_candidates,
    should_rotate_qwen_model,
)


def test_free_quota_exhausted_detection() -> None:
    assert is_qwen_free_quota_exhausted("AllocationQuota.FreeTierOnly")
    assert not is_qwen_free_quota_exhausted("invalid api key")


def test_rotation_on_quota_403() -> None:
    assert should_rotate_qwen_model(
        status=403,
        detail="AllocationQuota.FreeTierOnly",
        has_more_candidates=True,
    )


def test_default_text_rotation_uses_full_quota_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_TEXT_MODEL", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_TEXT_MODEL_ROTATION", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_LOW_QUOTA_MODELS", raising=False)
    candidates = qwen_text_model_candidates()
    assert candidates[0] == "qwen3.5-flash"
    assert "qwen-turbo" in candidates
    assert candidates[-1] == "qwen-turbo"


def test_low_quota_models_trail_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_TEXT_MODEL", raising=False)
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_LOW_QUOTA_MODELS", "qwen-turbo")
    candidates = qwen_text_model_candidates()
    assert candidates[0] == "qwen3.5-flash"
    assert candidates[-1] == "qwen-turbo"


def test_explicit_primary_kept_first_even_when_low_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_TEXT_MODEL", "qwen-turbo")
    monkeypatch.setenv("HARDWARE_SPLICER_QWEN_LOW_QUOTA_MODELS", "qwen-turbo")
    candidates = qwen_text_model_candidates()
    assert candidates[0] == "qwen-turbo"


def test_compose_stage_uses_coder_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "HARDWARE_SPLICER_QWEN_COMPOSE_MODEL",
        "HARDWARE_SPLICER_QWEN_COMPOSE_MODEL_ROTATION",
        "HARDWARE_SPLICER_QWEN_TEXT_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    candidates = qwen_text_model_candidates(stage="compose")
    assert candidates[0] == "qwen3-coder-flash"
    assert "qwen3.5-flash" in candidates


def test_workshop_stage_uses_plus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_WORKSHOP_MODEL", raising=False)
    candidates = qwen_text_model_candidates(stage="workshop")
    assert candidates[0] == "qwen3.5-plus"


def test_narrative_stage_uses_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_NARRATIVE_MODEL", raising=False)
    candidates = qwen_text_model_candidates(stage="narrative")
    assert candidates[0] == "qwen-flash"


def test_vision_board_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_VISION_BOARD_MODEL", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_VISION_STAGE", raising=False)
    candidates = qwen_vision_model_candidates(stage="board")
    assert candidates[0] == "qwen3-vl-flash-2026-01-22"


def test_vision_ocr_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_VISION_OCR_MODEL", raising=False)
    candidates = qwen_vision_model_candidates(stage="ocr")
    assert candidates[0] == "qwen-vl-ocr-2025-11-20"


def test_vision_rotation_uses_fresh_vl_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_VISION_MODEL", raising=False)
    monkeypatch.delenv("HARDWARE_SPLICER_QWEN_VISION_MODEL_ROTATION", raising=False)
    candidates = qwen_vision_model_candidates()
    assert candidates[0] == "qwen3-vl-flash-2026-01-22"
    assert "qwen3-vl-flash" in candidates


def test_blocks_video_and_image_models() -> None:
    assert is_blocked_chat_model("wan2.6-t2v")
    assert is_blocked_chat_model("qwen-image-max")
    assert not is_blocked_chat_model("qwen3.5-flash")
