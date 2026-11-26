"""Salvage rover package: control logic, the MicroPython device file, and the PC self-test against a simulated rover."""
from __future__ import annotations

import ast
import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "hs-rover-salvage-a"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


logic = _load("rover_logic", "firmware/rover_logic.py")
CFG = json.loads((ROOT / "firmware/config.example.json").read_text())


def test_toy_motors_are_held_to_their_own_voltage_and_reverse_uses_the_other_input():
    assert abs(logic.max_duty(4.8, 8.0) - 0.6) < 1e-9 and logic.max_duty(9.0, 7.4) == 1.0 and logic.max_duty(4.8, None) == 4.8 / 8.4
    assert logic.bridge(1.0, 0.5) == (32767, 0) and logic.bridge(-1.0, 0.5) == (0, 32767) and logic.bridge(0, 1) == (0, 0)


def test_commands_expire_the_battery_cutoff_refuses_and_bad_input_is_rejected():
    r = logic.Rover(CFG)
    r.tick(0, 7.6)
    assert r.handle("/drive?l=0.5&r=0.5&ms=300", 0)[0] == 200
    assert r.tick(100, 7.6)[0][0] > 0           # still within its 300 ms
    assert r.tick(400, 7.6) == ((0, 0), (0, 0))  # stopped on its own
    assert r.deadman_stops == 1
    assert r.handle("/drive?l=fast", 500)[0] == 400
    r.tick(600, 6.0)
    assert r.handle("/drive?l=0.5&r=0.5", 600)[0] == 503 and r.status(600)["low_battery"]
    fresh = logic.Rover(CFG); fresh.tick(0, 7.6)
    fresh.handle("/drive?l=1&r=1&ms=99999", 0)
    assert fresh.until_ms == logic.MAX_PULSE_MS  # a long request is cut to the 2 s maximum


def test_device_file_compiles_and_uses_only_modules_micropython_has():
    allowed = {"json", "socket", "time", "network", "machine", "rover_logic"}
    for rel in ("firmware/main.py", "firmware/rover_logic.py"):
        tree = ast.parse((ROOT / rel).read_text())
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert mods <= allowed | {"ujson"}, (rel, mods - allowed)
        assert not any(isinstance(n, (ast.AnnAssign,)) for n in ast.walk(tree)), rel


def test_selftest_passes_against_a_simulated_rover_running_the_same_logic(tmp_path):
    rover = logic.Rover(CFG)
    lock = threading.Lock()
    stop = threading.Event()

    def now():
        return int(time.monotonic() * 1000)

    def ticker():
        while not stop.is_set():
            with lock:
                rover.tick(now(), 7.6)
            time.sleep(0.02)

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            with lock:
                code, ctype, body = rover.handle(self.path, now())
            self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=ticker, daemon=True).start()
    try:
        selftest = _load("selftest", "tools/selftest.py")
        res = selftest.run(f"http://127.0.0.1:{srv.server_address[1]}", None)
    finally:
        stop.set(); srv.shutdown()
    assert res["passed"], [c for c in res["checks"] if not c["ok"]]
    assert "the wheels turned and the rover moved (record a video)" in res["not_checked_here"]
