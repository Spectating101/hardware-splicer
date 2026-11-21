from fastapi.testclient import TestClient

from hardware_splicer import api, digital_project


def test_startup_probes_runtimes_in_the_background(monkeypatch):
    calls = []
    monkeypatch.setenv("HARDWARE_SPLICER_PREWARM_RUNTIME", "1")
    monkeypatch.setattr(digital_project, "prewarm_runtimes", lambda: calls.append("probed"))
    started = []
    original = api._start_runtime_prewarm

    def start():
        thread = original()
        started.append(thread)
        return thread

    monkeypatch.setattr(api, "_start_runtime_prewarm", start)
    with TestClient(api.create_app()):
        pass
    assert started and started[0] is not None
    started[0].join(timeout=5)
    assert calls == ["probed"]


def test_prewarm_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_PREWARM_RUNTIME", "0")
    assert api._start_runtime_prewarm() is None


def test_prewarm_fills_the_probe_caches(monkeypatch):
    runs = []

    class Done:
        returncode = 0

    monkeypatch.setattr(digital_project.subprocess, "run", lambda *a, **k: runs.append(a[0]) or Done())
    digital_project._runtime.cache_clear()
    digital_project._device_runtime.cache_clear()
    try:
        digital_project.prewarm_runtimes()
        assert len(runs) == 3
        digital_project.runtime_for_case("fielddeck-5")
        digital_project.runtime()
        assert len(runs) == 3  # answered from the cache, no new interpreter
    finally:
        digital_project._runtime.cache_clear()
        digital_project._device_runtime.cache_clear()
