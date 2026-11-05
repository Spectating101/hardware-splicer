#!/usr/bin/env python3
"""HS PC bench collector: run ON the machine under test, from a live Linux USB.

Produces a directory of *raw tool output* plus ``manifest.json`` (sha256 of every
file, tool versions, timings, host fingerprint). ``casefile.py`` parses those raw
files; nothing in here decides pass/fail, so a typo in a parser cannot hide a
fault that the raw files still show.

Safety contract (enforced by tests/test_bench_collect_safety.py):
  * No disk writes of any kind: no mkfs/dd/wipefs -a/hdparm --security/nvme format.
    Storage is only *read* (smartctl -a, lsblk, wipefs --no-act, sampled reads).
  * Memory and CPU load run in RAM only (memtester, stress-ng --cpu/--vm).
  * Nothing is sent over the network except an optional ping to --ping-target.
  * Destructive sanitization is a separate, human-authorised step. --verify-wipe
    only *checks* the result afterwards.

Usage (as root, on the target):
  python3 bench_collect.py --out ./bundle --role target --memtest-mb 0 \
      --stress-seconds 1200 --selftest
  python3 bench_collect.py --out ./bundle --verify-wipe /dev/sda   # after wiping

The role ``control_host`` marks a machine that is NOT a salvaged unit; its bundle
can never release a product.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "hs.pc_bench_bundle.v1"
COLLECTOR_VERSION = "1"
ROLES = ("target", "control_host")
REDACT_KEYS = ("serial_number", "wwn", "eui64", "address", "broadcast", "local", "address_info")
SERIAL_LINE = re.compile(r"^(\s*(?:Serial Number|UUID|Asset Tag):\s*)(\S.*)$", re.M)


# ---------------------------------------------------------------- helpers
def safe_argv(argv: list[str]) -> list[str]:
    """Flags and non-path values only: the manifest must not leak local directory names."""
    out, skip = [], False
    for a in argv:
        if skip:
            out.append("<path>" if out[-1] == "--out" else "<addr>")
            skip = False
        elif a in ("--out", "--ping-target"):
            out.append(a)
            skip = True  # paths and network addresses are not recorded
        elif a == "--verify-wipe":
            out.append(a)  # a device node (/dev/sdX) is not sensitive
        else:
            out.append(a)
    return out


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tool(name: str) -> str | None:
    """Prefer HS_TOOL_DIR (a scratch unpack of the .deb) over PATH."""
    d = os.environ.get("HS_TOOL_DIR")
    if d:
        for sub in ("usr/sbin", "usr/bin", "sbin", "bin"):
            p = Path(d) / sub / name
            if p.is_file():
                return str(p)
    return shutil.which(name)


def run(cmd: list[str], timeout: float = 60) -> dict:
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"status": "ok", "rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
                "seconds": round(time.monotonic() - t0, 1), "cmd": cmd}
    except subprocess.TimeoutExpired as e:
        return {"status": "timeout", "rc": None, "stdout": (e.stdout or b"").decode("utf-8", "replace")
                if isinstance(e.stdout, bytes) else (e.stdout or ""), "stderr": "", "cmd": cmd,
                "seconds": round(time.monotonic() - t0, 1)}
    except OSError as e:
        return {"status": "error", "rc": None, "stdout": "", "stderr": str(e), "cmd": cmd, "seconds": 0.0}


MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _tok(v: str) -> str:
    return "redacted:" + hashlib.sha256(v.strip().encode()).hexdigest()[:8]


def redact_text(text: str) -> str:
    text = SERIAL_LINE.sub(lambda m: m.group(1) + _tok(m.group(2)), text)
    return IPV4.sub(lambda m: _tok(m.group(0)), MAC.sub(lambda m: _tok(m.group(0)), text))


def redact_json(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in REDACT_KEYS and v not in (None, "", [], {}):
                out[k] = _tok(json.dumps(v, sort_keys=True))
            else:
                out[k] = redact_json(v)
        return out
    if isinstance(obj, list):
        return [redact_json(x) for x in obj]
    return obj


class Bundle:
    def __init__(self, out: Path, redact: bool):
        self.out, self.redact, self.files, self.notes = out, redact, [], []
        out.mkdir(parents=True, exist_ok=True)

    def text(self, name: str, content: str) -> None:
        if self.redact:
            content = redact_text(content)
        (self.out / name).write_text(content, encoding="utf-8")
        self.files.append(name)

    def js(self, name: str, obj) -> None:
        if self.redact:
            obj = redact_json(obj)
        (self.out / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                                     encoding="utf-8")
        self.files.append(name)

    def finish(self, meta: dict) -> dict:
        digests = {n: hashlib.sha256((self.out / n).read_bytes()).hexdigest() for n in sorted(set(self.files))}
        manifest = {"schema": SCHEMA, "collector_version": COLLECTOR_VERSION, "finished_utc": now(),
                    "files_sha256": digests, "notes": self.notes, **meta}
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest


# ---------------------------------------------------------------- steps
def step_identity(b: Bundle) -> None:
    for name, cmd in (("dmidecode.txt", ["dmidecode", "-t", "system", "-t", "baseboard", "-t", "bios", "-t", "processor", "-t", "memory"]),
                      ("lsusb.txt", ["lsusb"]), ("lspci.txt", ["lspci"]),
                      ("dmesg_err.txt", ["dmesg", "--level=err,crit,alert,emerg"])):
        exe = tool(cmd[0])
        r = run([exe, *cmd[1:]]) if exe else {"status": "tool_missing", "stdout": "", "rc": None}
        good = r["status"] == "ok" and r.get("rc") == 0 and r["stdout"].strip()
        b.text(name, r["stdout"] if good else
               f"# HS_FAILED status={r['status']} rc={r.get('rc')} stderr={r.get('stderr','')[:200]!r}\n")
    b.text("cpuinfo.txt", Path("/proc/cpuinfo").read_text(errors="replace"))
    b.text("meminfo.txt", Path("/proc/meminfo").read_text(errors="replace"))
    b.text("uptime.txt", Path("/proc/uptime").read_text())
    u = platform.uname()  # node name (hostname) deliberately omitted
    b.js("platform.json", {"system": u.system, "release": u.release, "machine": u.machine,
                           "python": platform.python_version()})
    lsblk = tool("lsblk")
    r = run([lsblk, "--json", "--bytes", "-o", "NAME,TYPE,SIZE,ROTA,TRAN,MODEL,FSTYPE,PARTTYPE,MOUNTPOINT"]) if lsblk else None
    good = r and r["status"] == "ok" and r.get("rc") == 0 and r["stdout"].strip()
    b.text("lsblk.json", r["stdout"] if good else "# HS_FAILED lsblk did not produce output\n")


def disks() -> list[str]:
    lsblk = tool("lsblk")
    if not lsblk:
        return []
    r = run([lsblk, "-dn", "-o", "NAME,TYPE"])
    return [f"/dev/{l.split()[0]}" for l in r["stdout"].splitlines() if len(l.split()) == 2 and l.split()[1] == "disk"]


def selftest_running(smart_json: str) -> bool | None:
    """True = running, False = finished, None = could not tell (empty/garbled read: keep waiting, do not assume done)."""
    try:
        j = json.loads(smart_json)
    except ValueError:
        return None
    if not isinstance(j, dict):
        return None
    ata = j.get("ata_smart_data", {}).get("self_test", {}).get("status", {}).get("value")
    if ata is not None:
        return ata >> 4 == 15  # 0xF0..0xFF = self-test in progress
    nvme = j.get("nvme_self_test_log", {}).get("current_self_test_operation", {}).get("value")
    if nvme is not None:
        return bool(nvme)
    return None


def step_storage(b: Bundle, selftest: bool) -> None:
    sm = tool("smartctl")
    for dev in disks():
        name = "smart_" + dev.replace("/dev/", "") + ".json"
        if not sm:
            b.js(name, {"hs_status": "tool_missing"})
            continue
        if selftest:
            t = run([sm, "-t", "short", dev], 30)  # non-destructive firmware self-test
            # Keep the command's own answer: a drive can ignore the request, and its log is not always trustworthy.
            b.js("selftest_" + dev.replace("/dev/", "") + ".json",
                 {"requested": "short", "rc": t.get("rc"), "status": t["status"],
                  "began": "has begun" in t["stdout"].lower(), "stdout_tail": t["stdout"][-500:]})
            deadline, unreadable = time.monotonic() + 900, 0
            while time.monotonic() < deadline:
                time.sleep(15)
                state = selftest_running(run([sm, "-a", "-j", dev], 60)["stdout"])
                if state is False:
                    break
                unreadable = unreadable + 1 if state is None else 0
                if unreadable >= 6:  # the drive will not tell us; stop waiting, the gate will see no completed self-test
                    break
        r = run([sm, "-a", "-j", "-n", "standby,0", dev], 90)
        try:
            b.js(name, json.loads(r["stdout"]))
        except ValueError:
            b.js(name, {"hs_status": "unparseable", "stderr": r["stderr"][:300]})


def step_memory(b: Bundle, mb: int, loops: int) -> None:
    meminfo = Path("/proc/meminfo").read_text()
    total_mb = int(re.search(r"MemTotal:\s+(\d+)", meminfo).group(1)) // 1024
    avail_mb = int(re.search(r"MemAvailable:\s+(\d+)", meminfo).group(1)) // 1024
    if mb < 0:  # auto: 85% of what is currently free
        mb = int(avail_mb * 0.85)
    exe = tool("memtester")
    if not exe or mb == 0:
        b.js("memtester.meta.json", {"hs_status": "not_run", "reason": "tool_missing" if not exe else "disabled",
                                     "total_mb": total_mb})
        return
    r = run([exe, f"{mb}M", str(loops)], timeout=6 * 3600)
    b.text("memtester.txt", r["stdout"] + "\n--stderr--\n" + r["stderr"])
    b.js("memtester.meta.json", {"hs_status": "ran", "tested_mb": mb, "loops": loops, "rc": r["rc"],
                                 "total_mb": total_mb, "avail_mb_before": avail_mb, "seconds": r["seconds"]})


def read_temps() -> dict[str, float]:
    out = {}
    for p in Path("/sys/class/hwmon").glob("hwmon*/temp*_input"):
        try:
            label = (p.parent / "name").read_text().strip() + "/" + p.name.replace("_input", "")
            out[label] = int(p.read_text()) / 1000
        except (OSError, ValueError):
            pass
    return out


def throttle_counts() -> dict[str, int]:
    out = {}
    for p in Path("/sys/devices/system/cpu").glob("cpu*/thermal_throttle/*_throttle_count"):
        try:
            out[f"{p.parent.parent.name}/{p.name}"] = int(p.read_text())
        except (OSError, ValueError):
            pass
    return out


def step_thermal(b: Bundle, seconds: int) -> None:
    exe = tool("stress-ng")
    if not exe or seconds <= 0:
        b.js("thermal.json", {"hs_status": "not_run", "reason": "tool_missing" if not exe else "disabled"})
        return
    samples, stop = [], threading.Event()

    def sample():
        t0 = time.monotonic()
        while not stop.is_set():
            samples.append({"t": round(time.monotonic() - t0, 1), "temps_c": read_temps()})
            stop.wait(5)

    before = throttle_counts()
    th = threading.Thread(target=sample, daemon=True)
    th.start()
    # RAM + CPU only; never --hdd/--io/--sync-file, which would write to disks.
    r = run([exe, "--cpu", "0", "--vm", "1", "--vm-bytes", "50%", "--timeout", f"{seconds}s", "--metrics-brief"],
            timeout=seconds + 120)
    stop.set()
    th.join(timeout=10)
    after = throttle_counts()
    b.text("stress.txt", r["stdout"] + "\n--stderr--\n" + r["stderr"])
    b.js("thermal.json", {"hs_status": "ran", "requested_seconds": seconds, "rc": r["rc"], "wall_seconds": r["seconds"],
                          "samples": samples, "throttle_before": before, "throttle_after": after})


def step_network(b: Bundle, ping_target: str | None) -> None:
    ip = tool("ip")
    r = run([ip, "-j", "addr"]) if ip else None
    try:
        b.js("ip_addr.json", json.loads(r["stdout"]) if r and r["status"] == "ok" else [])
    except ValueError:
        b.js("ip_addr.json", {"hs_status": "unparseable"})
    if ping_target:
        ping = tool("ping")
        pr = run([ping, "-c", "5", "-W", "2", ping_target], 30) if ping else None
        out = pr["stdout"] if pr else ""
        target = ping_target
        if b.redact:
            out, target = redact_text(out), _tok(ping_target)
        b.js("ping.json", {"target": target, "rc": pr["rc"] if pr else None, "stdout": out})


def verify_wipe(b: Bundle, dev: str, samples: int = 128) -> None:
    """Read-only check that `dev` carries no filesystem signature and sampled blocks look sanitized."""
    wf = tool("wipefs")
    sig = run([wf, "--no-act", "--json", dev]) if wf else {"status": "tool_missing", "stdout": ""}
    bd = run([tool("blockdev") or "blockdev", "--getsize64", dev])
    m = re.fullmatch(r"\d+", bd["stdout"].strip()) if bd["status"] == "ok" and bd.get("rc") == 0 else None
    size = int(m.group(0)) if m else 0
    if size <= 0:  # cannot size the device: record that, never read an unknown device
        b.js("wipe_" + dev.replace("/dev/", "") + ".json", {
            "device": dev, "hs_status": "size_unavailable", "size_bytes": 0, "sampled_blocks": 0, "zero_blocks": 0,
            "signatures_stdout": sig["stdout"], "signature_rc": sig.get("rc"), "signature_tool": "size_unavailable",
            "min_entropy_bits_per_byte": None, "operator_declared_method": os.environ.get("HS_WIPE_METHOD", "unspecified"),
            "note": "blockdev --getsize64 failed; nothing was sampled"})
        return
    rng = random.SystemRandom()
    offsets = [0, max(0, size - (1 << 20))] + [rng.randrange(0, max(1, size - 4096)) // 4096 * 4096 for _ in range(samples)]
    zero_blocks, entropies = 0, []
    with open(dev, "rb", buffering=0) as f:  # read-only
        for off in offsets:
            f.seek(off)
            blk = f.read(4096)
            if not blk:
                continue
            if not any(blk):
                zero_blocks += 1
            counts = [0] * 256
            for byte in blk:
                counts[byte] += 1
            entropies.append(-sum(c / len(blk) * math.log2(c / len(blk)) for c in counts if c))
    n = len(entropies)
    b.js("wipe_" + dev.replace("/dev/", "") + ".json", {
        "device": dev, "size_bytes": size, "signatures_stdout": sig["stdout"], "signature_rc": sig.get("rc"),
        "signature_tool": "ok" if sig["status"] == "ok" and sig.get("rc") == 0 else sig["status"] + f"_rc{sig.get('rc')}",
        "sampled_blocks": n, "zero_blocks": zero_blocks,
        "min_entropy_bits_per_byte": round(min(entropies), 3) if entropies else None,
        "operator_declared_method": os.environ.get("HS_WIPE_METHOD", "unspecified"),
        "note": "Sampling proves nothing about unread sectors; it detects an unwiped or partially wiped disk."})


# ---------------------------------------------------------------- main
VERSION_FLAGS = {"smartctl": ["--version"], "stress-ng": ["--version"], "dmidecode": ["--version"],
                 "lsblk": ["--version"], "ip": ["-V"], "memtester": []}


def tool_versions() -> dict:
    """First line of each tool's own version output (memtester has no flag: its usage text carries the version)."""
    out = {"python": platform.python_version()}
    for name, flags in VERSION_FLAGS.items():
        exe = tool(name)
        if not exe:
            out[name] = None
            continue
        r = run([exe, *flags], 10)
        text = (r["stdout"] or r["stderr"] or "").strip().splitlines()
        out[name] = next((l.strip()[:120] for l in text if re.search(r"\d+\.\d+", l)), "unknown")
    return out


def fingerprint(out: Path) -> str:
    """Stable id from hardware identity files; equal across re-runs on the same machine."""
    h = hashlib.sha256()
    for n in ("dmidecode.txt", "lsblk.json"):
        p = out / n
        if p.exists():
            h.update(re.sub(r"\s+", " ", p.read_text(errors="replace")).encode())
    return h.hexdigest()[:16]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--role", choices=ROLES, default="target")
    ap.add_argument("--memtest-mb", type=int, default=0, help="0=skip, -1=auto 85%% of free RAM")
    ap.add_argument("--memtest-loops", type=int, default=2)
    ap.add_argument("--stress-seconds", type=int, default=0)
    ap.add_argument("--selftest", action="store_true", help="run SMART short self-test (non-destructive)")
    ap.add_argument("--ping-target", default=None)
    ap.add_argument("--redact-serials", action="store_true")
    ap.add_argument("--verify-wipe", metavar="DEV", default=None)
    a = ap.parse_args(argv)

    if a.out.exists() and any(a.out.iterdir()):
        raise SystemExit(f"refusing to reuse a non-empty output directory: stale files from an earlier run would sit "
                         f"beside this run's manifest. Choose a new --out.")
    b = Bundle(a.out, redact=a.redact_serials)
    started = now()
    if a.verify_wipe:
        verify_wipe(b, a.verify_wipe)
        meta = {"mode": "verify_wipe", "role": a.role, "started_utc": started, "argv": safe_argv(sys.argv[1:])}
    else:
        step_identity(b)
        step_storage(b, a.selftest)
        step_memory(b, a.memtest_mb, a.memtest_loops)
        step_thermal(b, a.stress_seconds)
        step_network(b, a.ping_target)
        meta = {"mode": "bench", "role": a.role, "started_utc": started, "argv": safe_argv(sys.argv[1:]),
                "redacted_serials": a.redact_serials, "host_fingerprint": fingerprint(a.out),
                "euid": os.geteuid(),
                "tools": {t: bool(tool(t)) for t in ("dmidecode", "smartctl", "memtester", "stress-ng", "lsblk", "ip")},
                "tool_versions": tool_versions()}
    m = b.finish(meta)
    print(f"bundle: {a.out}  role={m['role']}  files={len(m['files_sha256'])}  fingerprint={m.get('host_fingerprint')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
