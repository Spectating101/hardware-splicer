"""Opt-in, read-only Linux evdev BTN_LEFT observer; normalized JSONL only.

This cannot identify a physical donor, validate safety, inject input, grab a
device, construct hardware, or prove an attached device's provenance.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import select
import stat
import struct
import sys
import time
from collections.abc import Iterable, Iterator

EV_SYN = 0
SYN_DROPPED = 3
EV_KEY = 1
BTN_LEFT = 0x110
INPUT_EVENT = struct.Struct("@llHHi")  # kernel native struct input_event
_CAP_BYTES = BTN_LEFT // 8 + 1


class ObservationRefused(ValueError):
    """No trustworthy observed state available."""


def _alias(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is None:
        raise ObservationRefused("alias must be 1-64 ASCII letters, numbers, _ or -")
    return value


def _symbol(kind: str, alias: str) -> dict[str, str]:
    result = {"type": kind, "device": alias}
    if kind in {"pressed", "released"}:
        result["button"] = "left"
    return result


def _translate(kind: int, code: int, value: int, alias: str) -> dict[str, str] | None:
    if kind == EV_SYN and code == SYN_DROPPED:
        raise ObservationRefused("kernel SYN_DROPPED: state lost, discard capture")
    if kind != EV_KEY or code != BTN_LEFT:
        return None
    if value == 2:
        return None  # auto-repeat cannot become a second action
    if value == 1:
        return _symbol("pressed", alias)
    if value == 0:
        return _symbol("released", alias)
    raise ObservationRefused("invalid BTN_LEFT state")


def decode_chunks(chunks: Iterable[bytes], *, alias: str) -> Iterator[dict[str, str]]:
    """Pure decoder for offline tests; partial event records are not accepted."""
    alias = _alias(alias)
    pending = b""
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise ObservationRefused("input chunks must be bytes")
        pending += chunk
        if len(pending) > 65536:
            raise ObservationRefused("buffer limit")
        while len(pending) >= INPUT_EVENT.size:
            record, pending = pending[:INPUT_EVENT.size], pending[INPUT_EVENT.size:]
            _, _, kind, code, value = INPUT_EVENT.unpack(record)
            normalized = _translate(kind, code, value, alias)
            if normalized is not None:
                yield normalized
    if pending:
        raise ObservationRefused("truncated evdev input_event")


def _require_left_button(fd: int) -> None:
    """Getter EVIOCGBIT(EV_KEY), not an input modifier or donor identity proof."""
    command = (2 << 30) | (_CAP_BYTES << 16) | (ord("E") << 8) | (0x20 + EV_KEY)
    bits = bytearray(_CAP_BYTES)
    fcntl.ioctl(fd, command, bits, True)
    if not bits[BTN_LEFT // 8] & (1 << (BTN_LEFT % 8)):
        raise ObservationRefused("selected node does not advertise BTN_LEFT")


def open_device(path: str) -> int:
    if re.fullmatch(r"/dev/input/event[0-9]+", path) is None:
        raise ObservationRefused("select explicit /dev/input/eventN; no auto-probing or symlinks")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        if not stat.S_ISCHR(os.fstat(fd).st_mode):
            raise ObservationRefused("not an input character node")
        _require_left_button(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def observe(fd: int, *, alias: str, seconds: float, max_events: int) -> Iterator[dict[str, str]]:
    alias = _alias(alias)
    if not 0 < seconds <= 300 or not 0 < max_events <= 10000:
        raise ObservationRefused("require bounded <=300s duration and <=10000 button events")
    deadline = time.monotonic() + seconds
    pending = b""
    count = 0
    yield _symbol("connected", alias)
    try:
        while count < max_events:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                break
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                continue
            if not chunk:
                raise ObservationRefused("event device disconnected")
            pending += chunk
            if len(pending) > 65536:
                raise ObservationRefused("buffer limit")
            while len(pending) >= INPUT_EVENT.size:
                record, pending = pending[:INPUT_EVENT.size], pending[INPUT_EVENT.size:]
                _, _, kind, code, value = INPUT_EVENT.unpack(record)
                normalized = _translate(kind, code, value, alias)
                if normalized:
                    yield normalized
                    count += 1
                    if count >= max_events:
                        break
        if pending:
            raise ObservationRefused("capture ended with partial event")
    except GeneratorExit:
        # Cancellation must not try to yield from GeneratorExit.
        raise
    except BaseException:
        yield _symbol("disconnected", alias)
        raise
    else:
        yield _symbol("disconnected", alias)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read only one explicitly selected Linux mouse-button event stream. No injection, grab, or device discovery.")
    parser.add_argument("--device", required=True, help="explicit /dev/input/eventN")
    parser.add_argument("--alias", default="donor_mouse")
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--max-events", type=int, default=100)
    parser.add_argument("--consent-to-read-input", action="store_true")
    args = parser.parse_args(argv)
    if not args.consent_to_read_input:
        parser.error("--consent-to-read-input is mandatory")
    try:
        _alias(args.alias)
        if not 0 < args.seconds <= 300 or not 0 < args.max_events <= 10000:
            raise ObservationRefused("capture limits exceeded")
        fd = open_device(args.device)
        try:
            for event in observe(fd, alias=args.alias, seconds=args.seconds, max_events=args.max_events):
                print(json.dumps(event, sort_keys=True), flush=True)
        finally:
            os.close(fd)
    except (ObservationRefused, OSError, ValueError, KeyboardInterrupt) as exc:
        print("read-only observation stopped: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
