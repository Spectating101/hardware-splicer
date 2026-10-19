"""Independent behavioral oracle for normalized-event software reuse.

The oracle deliberately does not import or reuse the adapter's state machine.
No host input devices, injection, power, or hardware are accessed.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import types
import zipfile

import pytest

from hardware_splicer.intact_reuse_adapter import Adapter


REPO = Path(__file__).resolve().parents[1]
FROZEN_ZIP = REPO / "docs/status/generated/intact-reuse-2026-10-19/intact-input-review.zip"
FROZEN_SHA = "0751000fb19909800564e3a84c8bd9f0887abeda4e40392f43ba4b772ea7cc29"


def _oracle(events, device="mouse", button="left", action="activate"):
    """Contract: reconnect disarms; selected release arms; first press fires once."""
    connected = False
    armed = False
    outputs = []
    for step, event in enumerate(events):
        if event["device"] != device:
            continue
        kind = event["type"]
        if kind == "disconnected":
            connected, armed = False, False
        elif kind == "connected":
            connected, armed = True, False
        elif connected and event["button"] == button:
            if kind == "released":
                armed = True
            elif kind == "pressed" and armed:
                armed = False
                outputs.append((step, {"type": "action", "device_alias": device, "action": action}))
    return outputs


def _samples(seed):
    rng = random.Random(seed)
    devices = ["mouse", "mouse_other"]
    buttons = ["left", "right"]
    kinds = ["connected", "disconnected", "pressed", "released"]
    events = []
    for _ in range(180):
        kind = rng.choices(kinds, [1, 1, 5, 4])[0]
        device = rng.choices(devices, [5, 2])[0]
        event = {"type": kind, "device": device}
        if kind in ("pressed", "released"):
            event["button"] = rng.choice(buttons)
        events.append(event)
    return events


def _delivered_adapter():
    data = FROZEN_ZIP.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FROZEN_SHA
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        source = archive.read("adapter.py")
        binding = json.loads(archive.read("contract.json"))["interface"]
    module = types.ModuleType("independent_frozen_adapter")
    exec(compile(source, "<verified delivered adapter>", "exec"), module.__dict__)
    return module.Adapter, binding


@pytest.mark.parametrize("seed", range(40))
def test_long_interleaved_event_streams_match_independent_oracle(seed):
    events = _samples(seed)
    before = copy.deepcopy(events)
    adapter = Adapter("mouse", "left", "activate")
    actual = [(i, output) for i, event in enumerate(events) for output in adapter.feed(event)]
    assert actual == _oracle(events)
    assert events == before  # The replay must not rewrite the source observations.


@pytest.mark.parametrize("seed", range(10))
def test_exact_frozen_delivery_matches_independent_oracle(seed):
    adapter_type, binding = _delivered_adapter()
    events = _samples(seed + 1000)
    events = [
        {**event,
         "device": binding["device_alias"] if event["device"] == "mouse" else binding["device_alias"] + "_other",
         **({"button": binding["button"] if event["button"] == "left" else binding["button"] + "_other"}
            if "button" in event else {})}
        for event in events
    ]
    adapter = adapter_type(**binding)
    actual = [(i, output) for i, event in enumerate(events) for output in adapter.feed(event)]
    assert actual == _oracle(events, binding["device_alias"], binding["button"], binding["action"])
