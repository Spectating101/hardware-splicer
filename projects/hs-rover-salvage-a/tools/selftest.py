"""Test a built salvage rover over Wi-Fi from a PC and write the evidence.

    python selftest.py --rover http://192.168.1.50 [--phone http://192.168.1.51:8080/video] [--out evidence.json]

Checks what software can check: the rover answers, reports a battery voltage in range, accepts drive commands, stops on
its own when commands stop (the dead-man stop), refuses nothing it should accept, and (with --phone) the phone's video
stream delivers frames. Whether the wheels actually turned and the rover moved is not visible from here: record that as
a video. Lifting the rover so its wheels are off the ground during the test is the safe way to run it.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request


def get(url: str, timeout: float = 3.0) -> tuple[int, bytes, float]:
    t = time.monotonic()
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 - the user's own rover on the LAN
        body = r.read()
        return r.status, body, (time.monotonic() - t) * 1000


def status(base: str) -> dict:
    return json.loads(get(base + "/status")[1])


def stream_fps(url: str, seconds: float) -> dict:
    frames, got, t0 = 0, 0, time.monotonic()
    with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310
        while time.monotonic() - t0 < seconds:
            chunk = r.read(16384)
            if not chunk:
                break
            got += len(chunk)
            frames += chunk.count(b"\xff\xd8\xff")
    dt = time.monotonic() - t0
    return {"frames": frames, "seconds": round(dt, 2), "fps": round(frames / dt, 1) if dt else 0, "bytes": got}


def run(rover: str, phone: str | None, battery_range=(6.0, 8.6)) -> dict:
    base = rover.rstrip("/")
    checks = []

    def check(name, ok, **detail):
        checks.append({"check": name, "ok": bool(ok), **detail})

    lat = [get(base + "/status")[2] for _ in range(5)]
    s0 = status(base)
    check("answers", True, status_ms_median=round(statistics.median(lat), 1))
    v = s0.get("battery_v")
    check("battery voltage in range", v is not None and battery_range[0] <= v <= battery_range[1] and not s0.get("low_battery"),
          battery_v=v, range=list(battery_range), low_battery=s0.get("low_battery"))
    c0 = s0["commands"]
    code = get(base + "/drive?l=0.3&r=0.3&ms=300")[0]
    moving = status(base)["moving"]
    time.sleep(0.9)
    s1 = status(base)
    check("accepts a drive command", code == 200 and s1["commands"] == c0 + 1, http=code)
    check("stops on its own when commands stop", moving and not s1["moving"] and s1["deadman_stops"] > s0["deadman_stops"],
          moving_after_command=moving, moving_after_900ms=s1["moving"])
    for name, q in (("spin left", "l=-0.4&r=0.4"), ("spin right", "l=0.4&r=-0.4"), ("reverse", "l=-0.3&r=-0.3")):
        code = get(base + "/drive?" + q + "&ms=200")[0]
        check(name + " accepted", code == 200, http=code)
    get(base + "/stop")
    check("stop clears motion", not status(base)["moving"])
    bad = None
    try:
        get(base + "/drive?l=fast")
    except urllib.error.HTTPError as e:  # noqa: PERF203
        bad = e.code
    check("rejects a malformed command", bad == 400, http=bad)
    if phone:
        try:
            f = stream_fps(phone, 5.0)
            check("phone video streams", f["fps"] >= 5, **f)
        except Exception as e:  # noqa: BLE001
            check("phone video streams", False, error=f"{type(e).__name__}: {e}"[:200])
    return {"schema": "hardware_splicer.rover_selftest.v1", "rover": base, "phone": phone, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "passed": all(c["ok"] for c in checks), "checks": checks, "final_status": status(base),
            "not_checked_here": ["the wheels turned and the rover moved (record a video)", "runtime on a full charge",
                                 "driving on floors, rugs and thresholds", "the phone stays mounted"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rover", required=True); ap.add_argument("--phone"); ap.add_argument("--out", default="evidence.json")
    a = ap.parse_args(argv)
    res = run(a.rover, a.phone)
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1)
    for c in res["checks"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"])
    print("evidence written to", a.out)
    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
