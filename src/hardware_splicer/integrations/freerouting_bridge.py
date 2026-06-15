"""FreeRouting autorouter bridge via KiCad Specctra DSN/SES (pcbnew subprocess)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

FREEROUTING_VERSION = os.environ.get("HARDWARE_SPLICER_FREEROUTING_VERSION", "2.1.0")
FREEROUTING_JAR_URL = (
    f"https://github.com/freerouting/freerouting/releases/download/v{FREEROUTING_VERSION}/"
    f"freerouting-{FREEROUTING_VERSION}.jar"
)
DEFAULT_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hardware-splicer" / "freerouting"


def _resolve_freerouting_jar() -> Optional[Path]:
    env = os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR")
    if env and Path(env).is_file():
        return Path(env)
    cached = DEFAULT_CACHE / f"freerouting-{FREEROUTING_VERSION}.jar"
    if cached.is_file():
        return cached
    if not shutil.which("java"):
        return None
    try:
        DEFAULT_CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FREEROUTING_JAR_URL, cached)
        return cached if cached.is_file() else None
    except Exception:
        return None


def _ensure_pcbnew_importable() -> bool:
    try:
        import pcbnew  # noqa: F401

        return True
    except ImportError:
        for candidate in (
            "/usr/lib/python3/dist-packages",
            "/usr/lib/python3.13/dist-packages",
            "/usr/lib/python3.12/dist-packages",
        ):
            if candidate not in sys.path and Path(candidate).is_dir():
                sys.path.insert(0, candidate)
        try:
            import pcbnew  # noqa: F401

            return True
        except ImportError:
            return False


def _pcbnew_available() -> bool:
    return _ensure_pcbnew_importable()


def run_freerouting_pipeline(
    kicad_pcb_path: str | Path,
    *,
    out_dir: Optional[str | Path] = None,
    timeout_s: int = 600,
    threads: int = 1,
) -> Dict[str, Any]:
    """Export DSN → FreeRouting → import SES → save routed PCB."""
    pcb_in = Path(kicad_pcb_path)
    if not pcb_in.is_file():
        return {"ok": False, "skipped": True, "reason": "missing_pcb"}

    if not _pcbnew_available():
        return {"ok": False, "skipped": True, "reason": "pcbnew not available"}

    jar = _resolve_freerouting_jar()
    if not jar:
        return {"ok": False, "skipped": True, "reason": "freerouting jar/java unavailable"}

    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="hs-fr-"))
    work.mkdir(parents=True, exist_ok=True)
    dsn_path = work / "autoroute.dsn"
    ses_path = work / "autoroute.ses"
    pcb_out = work / "routed.kicad_pcb"

    try:
        import pcbnew

        board = pcbnew.LoadBoard(str(pcb_in))
        pcbnew.ExportSpecctraDSN(board, str(dsn_path))
        if not dsn_path.is_file() or dsn_path.stat().st_size < 100:
            return {"ok": False, "skipped": False, "reason": "dsn export failed"}

        cmd = [
            "java",
            "-jar",
            str(jar),
            "-de",
            str(dsn_path),
            "-do",
            str(ses_path),
            "-mt",
            str(max(1, threads)),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if proc.returncode != 0 or not ses_path.is_file():
            return {
                "ok": False,
                "skipped": False,
                "reason": "freerouting failed",
                "stderr": (proc.stderr or "")[-3000:],
                "stdout": (proc.stdout or "")[-1500:],
                "dsn_path": str(dsn_path),
            }

        pcbnew.ImportSpecctraSES(board, str(ses_path))
        pcbnew.SaveBoard(str(pcb_out), board)

        track_count = 0
        for _ in board.GetTracks():
            track_count += 1

        return {
            "ok": True,
            "skipped": False,
            "reason": "",
            "routed_pcb_path": str(pcb_out),
            "dsn_path": str(dsn_path),
            "ses_path": str(ses_path),
            "track_count": track_count,
            "freerouting_version": FREEROUTING_VERSION,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "skipped": False, "reason": "freerouting timeout"}
    except Exception as exc:
        return {"ok": False, "skipped": False, "reason": str(exc)}


def summarize_freerouting_for_quality(report: Mapping[str, Any]) -> Dict[str, Any]:
    if report.get("skipped"):
        return {
            "freerouting_ready": False,
            "freerouting_skipped": True,
            "freerouting_reason": report.get("reason"),
        }
    return {
        "freerouting_ready": True,
        "freerouting_skipped": False,
        "freerouting_ok": bool(report.get("ok")),
        "freerouting_track_count": int(report.get("track_count") or 0),
        "freerouting_routed_pcb": report.get("routed_pcb_path"),
        "freerouting_version": report.get("freerouting_version"),
    }
