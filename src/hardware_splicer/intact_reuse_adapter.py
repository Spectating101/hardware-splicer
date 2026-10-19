"""Offline, one-shot adapter for normalized host-button events.

This module neither reads USB nor injects OS input. Device aliases and button
names are proposed bindings, not decoded or measured donor facts. It is copied
unchanged into intact-reuse review bundles and tested there in isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


class Adapter:
    def __init__(self, device_alias: str, button: str, action: str):
        if not all(isinstance(value, str) and value for value in (device_alias, button, action)):
            raise ValueError("device_alias, button and action must be nonempty strings")
        self.device = device_alias
        self.button = button
        self.action = action
        self.state = "disconnected"

    def feed(self, event: dict) -> list[dict]:
        if not isinstance(event, dict) or set(event) - {"type", "device", "button"}:
            raise ValueError("event accepts only type, device and button")
        kind = event.get("type")
        if kind not in {"connected", "disconnected", "pressed", "released"}:
            raise ValueError("unknown event type")
        if not isinstance(event.get("device"), str) or not event["device"]:
            raise ValueError("event requires a device alias")
        if kind in {"pressed", "released"} and not isinstance(event.get("button"), str):
            raise ValueError("button event requires a button name")
        if event["device"] != self.device:
            return []
        if kind == "disconnected":
            self.state = "disconnected"
        elif kind == "connected":
            self.state = "wait_release"
        elif event["button"] == self.button and self.state != "disconnected":
            if kind == "released":
                self.state = "armed"
            elif self.state == "armed":
                self.state = "wait_release"
                return [{"type": "action", "action": self.action, "device_alias": self.device}]
        return []


def main() -> int:
    """JSONL in, symbolic actions out. Never auto-selects a real device."""
    try:
        contract = json.loads(Path(__file__).with_name("contract.json").read_text())
        adapter = Adapter(**contract["interface"])
        for line in sys.stdin:
            for action in adapter.feed(json.loads(line)):
                print(json.dumps(action, sort_keys=True), flush=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"adapter refused input: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
