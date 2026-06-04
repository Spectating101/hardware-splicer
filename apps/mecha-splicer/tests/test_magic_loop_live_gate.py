from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class _MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/health":
            body = json.dumps({"status": "healthy", "version": "mock"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/v2/workflow/validate-kicad":
            body = json.dumps({"status": "validation_passed", "validation": {"critical": 0, "errors": 0, "warnings": 0}}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args, **_kwargs):
        return


def test_magic_loop_calls_live_circuit_gate(tmp_path):
    server = HTTPServer(("127.0.0.1", 0), _MockHandler)
    host, port = server.server_address
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        repo = Path(__file__).resolve().parents[1]
        master = tmp_path / "master.json"
        master.write_text(
            json.dumps(
                {
                    "intent": {"name": "unit", "goal": "test", "environment": "indoor", "budget_usd": 100},
                    "electrical": {
                        "target_voltage_v": 5.0,
                        "max_current_a": 1.0,
                        "rails": [{"name": "3V3", "min_v": 3.0, "max_v": 3.6}],
                    },
                    "mechanical": {
                        "envelope_mm": {"w": 100, "d": 60, "h": 40},
                        "payload_n": 2.0,
                        "payload_offset_mm": 30.0,
                        "camera_pan_tilt": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        out_dir = tmp_path / "magic"
        subprocess.check_call(
            [
                "python3",
                "scripts/circuit_mecha_magic_loop.py",
                "--master-spec",
                str(master),
                "--out",
                str(out_dir),
                "--max-iters",
                "1",
                "--circuit-api-url",
                f"http://{host}:{port}",
            ],
            cwd=repo,
        )

        data = json.loads((out_dir / "MAGIC_LOOP_RESULT.json").read_text(encoding="utf-8"))
        remote = data["iterations"][0]["circuit_gate"]["remote"]
        assert remote["health"]["status_code"] == 200
        assert remote["validate_kicad"]["status_code"] == 200
    finally:
        server.shutdown()
