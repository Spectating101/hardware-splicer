#!/usr/bin/env python3
"""A local, plain-language replay of the mouse example. No hardware or AI call.

Planning is read from the retained real agent study. Interactions execute the
exact Python adapter in the retained software bundle, not a JavaScript copy.
There is no project mutation, credential, physical interface or external service.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import types
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SHA256 = "0751000fb19909800564e3a84c8bd9f0887abeda4e40392f43ba4b772ea7cc29"


class MouseDemo:
    def __init__(self, root=ROOT):
        self.page = (root / "examples/mouse-reuse-demo/index.html").read_bytes()
        self.bundle = (root / "docs/status/generated/intact-reuse-2026-10-19/intact-input-review.zip").read_bytes()
        if hashlib.sha256(self.bundle).hexdigest() != PACKAGE_SHA256:
            raise ValueError("frozen demonstration bundle does not match its expected hash")
        with zipfile.ZipFile(io.BytesIO(self.bundle)) as archive:
            if archive.testzip() is not None:
                raise ValueError("frozen bundle is corrupt")
            adapter_source = archive.read("adapter.py")
            contract = json.loads(archive.read("contract.json"))
        module = types.ModuleType("frozen_mouse_demo_adapter")
        exec(compile(adapter_source, "<hash-verified delivered adapter>", "exec"), module.__dict__)
        self.adapter_type = module.Adapter
        self.binding = contract["interface"]
        plan_path = root / "docs/status/generated/cold-usb-mouse-2026-10-19/store/cold-usb-mouse-document-study/revisions/00000004.json"
        plan_bytes = plan_path.read_bytes()
        plan = json.loads(plan_bytes)["snapshot"]["preFabricationPlan"]
        ids = [candidate["candidate_id"] for candidate in plan["architecture_candidates"]]
        if set(ids) != {"intact_pedal", "remote_contact"}:
            raise ValueError("recorded study no longer matches this worked example")
        self.story = {
            "kind": "recorded_agent_plan_live_delivered_program",
            "live_model": False, "physical_specimen": False,
            "agent_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "package_sha256": PACKAGE_SHA256, "recorded_candidate_ids": ids,
            "binding": self.binding,
            "planning_note": "The options shown are summarized from a saved agent run. No new AI session is running on this page.",
            "execution_note": "The buttons send pretend presses to the actual Python program from the saved bundle. They do not operate hardware or another application.",
        }

    def replay(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"events"}:
            raise ValueError("supply only an events list")
        events = payload["events"]
        if not isinstance(events, list) or len(events) > 512:
            raise ValueError("use a list of at most 512 pretend events; reset to start again")
        adapter = self.adapter_type(**self.binding)
        actions = []
        last_actions = []
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                raise ValueError("each event requires a text type")
            last_actions = adapter.feed(event)
            actions.extend(last_actions)
        return {"actions_triggered": len(actions), "last_event_actions": len(last_actions),
                "state": adapter.state, "event_count": len(events),
                "package_sha256": PACKAGE_SHA256, "physical_device_used": False}


def make_server(port=0, demo=None):
    demo = demo or MouseDemo()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, data, media="application/json", extra=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in hosts

        def do_GET(self):
            if not self.valid_host():
                return self.respond(403, {"error": "This demonstration is local only."})
            path = urlsplit(self.path).path
            if path == "/":
                return self.respond(200, demo.page, "text/html; charset=utf-8")
            if path == "/story":
                return self.respond(200, demo.story)
            if path == "/bundle.zip":
                return self.respond(200, demo.bundle, "application/zip", {"Content-Disposition": 'attachment; filename="mouse-reuse-software.zip"'})
            return self.respond(404, {"error": "Page not found."})

        def do_POST(self):
            if not self.valid_host() or self.headers.get("Origin") not in {None, f"http://{self.headers.get('Host')}"}:
                return self.respond(403, {"error": "Use this demonstration from its own local page."})
            if self.path != "/try":
                return self.respond(404, {"error": "Page not found."})
            if self.headers.get_content_type() != "application/json":
                return self.respond(415, {"error": "Use a JSON request."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    return self.respond(413, {"error": "This example accepts small requests only."})
                self.connection.settimeout(5)
                payload = json.loads(self.rfile.read(length))
                return self.respond(200, demo.replay(payload))
            except (ValueError, TypeError, KeyError, OSError):
                return self.respond(400, {"error": "That input could not be replayed. Reset the example and try again."})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Local port; default chooses an unused one")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    with make_server(args.port) as server:
        print(f"Mouse reuse demonstration: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
