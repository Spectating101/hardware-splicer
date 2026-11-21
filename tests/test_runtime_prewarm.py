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
        for case_id in ("fielddeck-5", "fielddeck-7", "ender3-penplotter"):
            digital_project.runtime_for_case(case_id)
        digital_project.runtime()
        assert len(runs) == 3  # every case is answered from a prewarmed entry, no new interpreter
    finally:
        digital_project._runtime.cache_clear()
        digital_project._device_runtime.cache_clear()


def test_a_request_waits_for_its_own_running_probe_but_not_for_others(monkeypatch):
    import threading

    runs = []
    release = threading.Event()
    device_started = threading.Event()

    class Done:
        returncode = 0

    def run(argv, **kwargs):
        runs.append(argv[-1])
        if "pydantic" in argv[-1]:  # the fielddeck-5 probe: held until released
            device_started.set()
            assert release.wait(5)
        return Done()

    monkeypatch.setattr(digital_project.subprocess, "run", run)
    digital_project._runtime.cache_clear()
    digital_project._device_runtime.cache_clear()
    try:
        digital_project.runtime()  # drone probe answered and cached
        probing = threading.Thread(target=digital_project.runtime_for_case, args=("fielddeck-5",))
        probing.start()
        assert device_started.wait(5)

        # A cached answer and a different probe are not held behind the running one.
        assert digital_project.runtime()["available"] is True
        assert digital_project.runtime_for_case("fielddeck-7")["available"] is True

        # The same probe waits for the running one instead of starting a second interpreter.
        waiting = threading.Thread(target=digital_project.runtime_for_case, args=("fielddeck-5",))
        waiting.start()
        waiting.join(0.3)
        assert waiting.is_alive()
        release.set()
        probing.join(5)
        waiting.join(5)
        assert sum("pydantic" in imports for imports in runs) == 1
        assert len(runs) == 3  # drone, fielddeck-5, fielddeck-7: nothing duplicated
    finally:
        release.set()
        digital_project._runtime.cache_clear()
        digital_project._device_runtime.cache_clear()
