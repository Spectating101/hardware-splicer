from fastapi.testclient import TestClient


def test_enhanced_api_proxy_health_and_metrics():
    from src.api.v1.main import app

    with TestClient(app) as client:
        health = client.get("/api/proxy/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "circuit-ai-backend"}

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "circuit_api_requests_total" in metrics.text
        assert "circuit_analysis_duration_seconds" in metrics.text
