from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_product_launchers_use_canonical_app_and_dedicated_port() -> None:
    canonical = _read("scripts/run_product_api.py")
    compatibility = _read("scripts/run_extended_product_api.py")

    for source in (canonical, compatibility):
        assert 'HARDWARE_SPLICER_API_PORT", "8090"' in source
        assert '"hardware_splicer.product_api:app"' in source
        assert 'HARDWARE_SPLICER_API_HOST", "127.0.0.1"' in source


def test_frontend_proxy_default_matches_product_launcher() -> None:
    backend = _read(
        "apps/circuit-ai/circuit-ai-frontend/app/api/proxy/_backend.ts"
    )

    assert 'DEFAULT_VISION_BASE_URL = "http://127.0.0.1:8000"' in backend
    assert 'DEFAULT_HARDWARE_SPLICER_URL = "http://127.0.0.1:8090"' in backend
    assert "return (" in backend
    assert 'envValue("HARDWARE_SPLICER_API_URL")' in backend
