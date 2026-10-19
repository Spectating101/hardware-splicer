"""Synthetic evdev bytes only: no real /dev/input access."""
import io
import json
import os
import stat
from unittest.mock import patch

import pytest

from hardware_splicer.host_mouse_observer import (
    BTN_LEFT, EV_KEY, EV_SYN, INPUT_EVENT, ObservationRefused,
    _require_left_button, decode_chunks, main, observe, open_device,
)
from hardware_splicer.intact_reuse_adapter import Adapter


def record(kind=EV_KEY, code=BTN_LEFT, value=1):
    return INPUT_EVENT.pack(123, 456, kind, code, value)


def test_filter_and_partial_native_records():
    stream = record(0, 0, 0) + record(2, 0, 37) + record(EV_KEY, 30, 1)
    stream += record(EV_KEY, 273, 1) + record(value=0) + record(value=1)
    stream += record(value=2) + record(value=0)
    events = list(decode_chunks([stream[:1], stream[1:13], stream[13:47], stream[47:]], alias="mouse"))
    assert events == [
        {"type": "released", "device": "mouse", "button": "left"},
        {"type": "pressed", "device": "mouse", "button": "left"},
        {"type": "released", "device": "mouse", "button": "left"},
    ]
    assert "123" not in json.dumps(events)


@pytest.mark.parametrize("data", [record(EV_SYN, 3, 0), record(value=4), record()[:-1]])
def test_bad_sync_value_partial_record_refused(data):
    with pytest.raises(ObservationRefused):
        list(decode_chunks([data], alias="mouse"))


@pytest.mark.parametrize("alias", ["", "a/b", "key board", "x" * 65])
def test_alias_must_be_nonidentifying_slug(alias):
    with pytest.raises(ObservationRefused):
        list(decode_chunks([record()], alias=alias))


def test_consent_required_before_opening(capsys):
    with patch("hardware_splicer.host_mouse_observer.open_device") as opened:
        with pytest.raises(SystemExit) as exc:
            main(["--device", "/dev/input/event3"])
        assert exc.value.code == 2
        opened.assert_not_called()
    assert "--consent-to-read-input" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["/etc/passwd", "/dev/input/by-id/foo", "/dev/input/event3/../event4", "/dev/input/eventx"])
def test_disallow_alias_paths_without_opening(bad):
    with patch("hardware_splicer.host_mouse_observer.os.open") as opened:
        with pytest.raises(ObservationRefused):
            open_device(bad)
        opened.assert_not_called()


def test_require_char_node_and_close_on_failure():
    with patch("hardware_splicer.host_mouse_observer.os.open", return_value=17) as opened, \
         patch("hardware_splicer.host_mouse_observer.os.fstat") as fst, \
         patch("hardware_splicer.host_mouse_observer.os.close") as closed:
        fst.return_value.st_mode = stat.S_IFREG | 0o644
        with pytest.raises(ObservationRefused):
            open_device("/dev/input/event7")
        flags = opened.call_args.args[1]
        assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
        assert (flags & os.O_ACCMODE) == os.O_RDONLY
        closed.assert_called_once_with(17)


def test_ioctl_capability_gate_only_gets_left_bit():
    bits = bytearray(BTN_LEFT // 8 + 1)

    def fake_ioctl(fd, op, target, mutable):
        assert fd == 18 and op & 0xff == 0x21 and mutable
        target[:] = bits

    with patch("hardware_splicer.host_mouse_observer.fcntl.ioctl", side_effect=fake_ioctl):
        with pytest.raises(ObservationRefused, match="does not advertise"):
            _require_left_button(18)
        bits[BTN_LEFT // 8] = 1 << (BTN_LEFT % 8)
        _require_left_button(18)


def test_readonly_stream_drives_actual_adapter_and_never_repeats():
    raw = record(value=1) + record(value=2) + record(value=0)
    raw += record(value=1) + record(value=1) + record(EV_KEY, 273, 1) + record(value=0)
    stream = io.BytesIO(raw)
    with patch("hardware_splicer.host_mouse_observer.select.select", return_value=([3], [], [])), \
         patch("hardware_splicer.host_mouse_observer.os.read", side_effect=lambda *_: stream.read(4096)):
        events = list(observe(3, alias="donor_mouse", seconds=15, max_events=5))
    assert events[0]["type"] == "connected"
    assert events[-1]["type"] == "disconnected"
    adapter = Adapter("donor_mouse", "left", "activate")
    actions = [a for e in events for a in adapter.feed(e)]
    assert actions == [{"type": "action", "action": "activate", "device_alias": "donor_mouse"}]
    assert all(set(e) <= {"type", "device", "button"} for e in events)


def test_kernel_sync_loss_refused():
    with patch("hardware_splicer.host_mouse_observer.select.select", return_value=([9], [], [])), \
         patch("hardware_splicer.host_mouse_observer.os.read", return_value=record(EV_SYN, 3, 0)):
        stream = observe(9, alias="mouse", seconds=1, max_events=1)
        assert next(stream)["type"] == "connected"
        with pytest.raises(ObservationRefused, match="SYN_DROPPED"):
            list(stream)


def test_bounds_refused_before_opening():
    with patch("hardware_splicer.host_mouse_observer.open_device") as opened:
        assert main(["--consent-to-read-input", "--device", "/dev/input/event2", "--seconds", "301"]) == 2
        assert main(["--consent-to-read-input", "--device", "/dev/input/event2", "--max-events", "0"]) == 2
        opened.assert_not_called()


def test_no_release_invented_when_idle():
    with patch("hardware_splicer.host_mouse_observer.select.select", return_value=([], [], [])):
        assert list(observe(3, alias="mouse", seconds=1, max_events=1)) == [
            {"type": "connected", "device": "mouse"},
            {"type": "disconnected", "device": "mouse"},
        ]


def test_early_close_does_not_yield_during_generator_exit():
    with patch("hardware_splicer.host_mouse_observer.select.select", return_value=([], [], [])):
        gen = observe(3, alias="mouse", seconds=1, max_events=1)
        assert next(gen)["type"] == "connected"
        gen.close()  # Should not raise RuntimeError('generator ignored GeneratorExit').
