"""Proposals and explicit offline trials. Evidence never grants approval."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .github_signal_pipeline import SignalEvaluationError, sha256_file
from .kicad_diff import parse_kicad_sexp

IBOM = "openscopeproject/InteractiveHtmlBom"
KIKIT = "yaqwsx/KiKit"
TRIAL_FILENAME = "HS_SIGNAL_PROPOSAL_TRIAL.json"
_IBOM_ARGV = [
    "bwrap", "--unshare-all", "--die-with-parent",
    "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib",
    "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin",
    "--ro-bind", "/etc", "/etc", "--proc", "/proc", "--dev", "/dev",
    "--tmpfs", "/tmp", "--ro-bind", "{checkout}", "/opt/ibom",
    "--ro-bind", "{board}", "/input/board.kicad_pcb",
    "--bind", "{out}", "/output", "--setenv", "HOME", "/tmp",
    "--setenv", "INTERACTIVE_HTML_BOM_NO_DISPLAY", "1", "--chdir", "/tmp",
    "/usr/bin/python3", "-B", "/opt/ibom/InteractiveHtmlBom/generate_interactive_bom.py",
    "--no-browser", "--dest-dir", "/output", "--name-format", "ibom",
    "/input/board.kicad_pcb",
]
_DEPENDENCIES = ["shapely", "markdown2", "pybars", "commentjson", "solidpython"]
_DEPENDENCY_BLOCKER = (
    "Missing host Python packages: " + ", ".join(_DEPENDENCIES) +
    "; runtime installation forbidden; requires a pinned, reviewed dependency environment"
)
PROPOSED_ADAPTERS = {
    IBOM: {
        "repository": IBOM,
        "proposed_commit": "5c192e794cd66fde04bab11810601b711bf8581b",
        "release": "v2.12.0", "license_claim": "MIT",
        "objective": "interactive assembly BOM / placement viewer for a KiCad board",
        "argv_template": _IBOM_ARGV,
        "required_host_capabilities": ["bwrap", "/usr/bin/python3", "pcbnew", "wx", "KiCad 9"],
        "expected_outputs": ["ibom.html"],
        "status": "proposed_pending_human_approval", "blockers": [],
        "trial_evidence": {
            "source": "operator-established offline trial",
            "argv_template": _IBOM_ARGV,
            "board": "hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb",
            "exit_code": 0, "output": "/output/ibom.html",
            "output_bytes_approx": 229000, "checkout_clean_after": True,
            "host": "/usr/bin/python3 with KiCad 9 pcbnew and wx",
            "other_dependencies": [], "installation": False, "network": False,
            "pcbdata_encoding": 'JSON.parse(LZString.decompressFromBase64("..."))',
            "references_match_board": True, "reference_count": 40,
            "bom_keys": ["both", "skipped", "fields", "F", "B"],
            "bom_both_rows": 10, "approval_effect": "none",
        },
    },
    KIKIT: {
        "repository": KIKIT,
        "proposed_commit": "d1957c535781371db5a2f507f8154d460095f9f1",
        "release": "v1.8.1", "license_claim": "MIT",
        "objective": "panelisation / fab outputs for a KiCad board",
        # Exact candidate panelisation command, NOT trialled or executable.
        "argv_template": [
            *[x.replace("/opt/ibom", "/opt/kikit")
              for x in _IBOM_ARGV[:_IBOM_ARGV.index("/usr/bin/python3")]],
            "--setenv", "PYTHONPATH", "/opt/kikit", "/usr/bin/python3", "-B",
            "-m", "kikit", "panelize", "/input/board.kicad_pcb", "/output/panel.kicad_pcb",
        ],
        "required_host_capabilities": ["bwrap", "/usr/bin/python3", "pcbnew", *_DEPENDENCIES],
        "expected_outputs": ["panel.kicad_pcb"],
        "status": "proposed_blocked", "blockers": [_DEPENDENCY_BLOCKER],
        "trial_evidence": {
            "source": "operator-established dependency assessment",
            "missing_host_packages": _DEPENDENCIES, "executed": False,
            "runtime_installation_forbidden": True, "approval_effect": "none",
        },
    },
}


def decompress_from_base64(value: str) -> str:
    """Decode LZString's LSB-first dictionary stream (6-bit Base64 alphabet).

    LZString uses UTF-16 code units and its own bit packing, not RFC 4648
    byte decoding. Bound both input and expanded output; reject bad streams.
    """
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    if not value or len(value) > 15 * 1024 * 1024 or not re.fullmatch(r"[A-Za-z0-9+/]+={0,3}", value):
        raise SignalEvaluationError("invalid LZString Base64")
    encoded = value.rstrip("=")
    position = 0

    def bits(width: int) -> int:
        nonlocal position
        result = 0
        for shift in range(width):
            if position >= len(encoded) * 6:
                raise SignalEvaluationError("truncated LZString stream")
            digit = alphabet.index(encoded[position // 6])
            result |= ((digit >> (5 - position % 6)) & 1) << shift
            position += 1
        return result

    marker = bits(2)
    if marker == 2:
        return ""
    if marker not in (0, 1):
        raise SignalEvaluationError("invalid LZString initial code")
    previous = chr(bits(8 if marker == 0 else 16))
    dictionary = ["", "", "", previous]
    result = [previous]
    width, remaining, expanded = 3, 4, 1
    while True:
        code = bits(width)
        if code == 2:
            # Combine surrogate pairs exactly as JavaScript UTF-16 strings do.
            return "".join(result).encode("utf-16-le", errors="surrogatepass").decode("utf-16-le")
        if code in (0, 1):
            dictionary.append(chr(bits(8 if code == 0 else 16)))
            code = len(dictionary) - 1
            remaining -= 1
        if remaining == 0:
            remaining = 1 << width
            width += 1
        if code < len(dictionary):
            entry = dictionary[code]
        elif code == len(dictionary):
            entry = previous + previous[0]
        else:
            raise SignalEvaluationError("invalid LZString dictionary code")
        expanded += len(entry)
        if expanded > 16 * 1024 * 1024:
            raise SignalEvaluationError("LZString expanded output exceeds 16 MiB")
        result.append(entry)
        dictionary.append(previous + entry[0])
        remaining -= 1
        previous = entry
        if remaining == 0:
            remaining = 1 << width
            width += 1


def check_ibom_output(board: Path, html: Path) -> dict[str, Any]:
    """Read board references and compressed page data without executing JS."""
    try:
        if board.stat().st_size > 12 * 1024 * 1024:
            raise SignalEvaluationError("board exceeds 12 MiB")
        tree = parse_kicad_sexp(board.read_text(encoding="utf-8"))
        if not tree or tree[0] != "kicad_pcb":
            raise SignalEvaluationError("expected a KiCad PCB")
        references = set()
        for node in tree[1:]:
            if not isinstance(node, list) or not node or node[0] not in {"footprint", "module"}:
                continue
            modern = [x[2] for x in node[1:] if isinstance(x, list) and len(x) >= 3
                      and x[:2] == ["property", "Reference"]]
            legacy = [x[2] for x in node[1:] if isinstance(x, list) and len(x) >= 3
                      and x[:2] == ["fp_text", "reference"]]
            refs = modern or legacy
            if len(refs) != 1 or not refs[0] or refs[0] in references:
                raise SignalEvaluationError("missing/duplicate board footprint reference")
            references.add(refs[0])
        if html.is_symlink() or not stat.S_ISREG(html.stat().st_mode) or html.stat().st_size > 15 * 1024 * 1024:
            raise SignalEvaluationError("iBOM output must be a regular HTML file under 15 MiB")
        matches = re.findall(
            r'\bvar\s+pcbdata\s*=\s*JSON\.parse\(\s*LZString\.decompressFromBase64\(\s*"([A-Za-z0-9+/=]+)"\s*\)\s*\)',
            html.read_text(encoding="utf-8"),
        )
        if len(matches) != 1:
            raise SignalEvaluationError("expected one compressed pcbdata assignment")
        data = json.loads(decompress_from_base64(matches[0]))
        if (not isinstance(data, dict) or not isinstance(data.get("bom"), dict)
                or not isinstance(data.get("footprints"), list)
                or any(not isinstance(x, dict) or not isinstance(x.get("ref"), str)
                       for x in data["footprints"])):
            raise SignalEvaluationError("pcbdata requires footprints[].ref and bom")
        actual = {x["ref"] for x in data["footprints"]}
        missing, extra = sorted(references - actual), sorted(actual - references)
        return {"ok": not missing and not extra, "missing_refs": missing,
                "extra_refs": extra, "board_reference_count": len(references),
                "output_reference_count": len(actual), "bom_present": True}
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        return {"ok": False, "error": str(exc)}


def _verify_checkout(checkout: Path, spec: dict[str, Any]) -> None:
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise SignalEvaluationError("trial requires a clean git checkout")
    env = {"PATH": os.defpath, "HOME": "/tmp", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(checkout), "-c", "core.fsmonitor=false", *args],
            capture_output=True, text=True, check=True, timeout=10, env=env, cwd="/",
        ).stdout.strip()
    if git("rev-parse", "--show-toplevel") != str(checkout):
        raise SignalEvaluationError("checkout must be the git root")
    pin = spec["proposed_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", pin) or git("rev-parse", "HEAD") != pin:
        raise SignalEvaluationError("checkout HEAD differs from full proposed commit")
    if git("status", "--porcelain", "--untracked-files=all", "--ignored=matching"):
        raise SignalEvaluationError("trial checkout dirty (including untracked/ignored files)")
    license_file = checkout / "LICENSE"
    if (spec["license_claim"] != "MIT" or license_file.is_symlink()
            or not license_file.is_file()
            or not license_file.read_text(encoding="utf-8").startswith("MIT License\n")):
        raise SignalEvaluationError("checkout LICENSE does not match MIT licence claim")
    entry = checkout / "InteractiveHtmlBom/generate_interactive_bom.py"
    if not entry.is_file() or not entry.resolve().is_relative_to(checkout):
        raise SignalEvaluationError("trial entrypoint absent or escaping checkout")


def _host_capabilities(bwrap: str) -> dict[str, Any]:
    capabilities: dict[str, Any] = {"bwrap": bwrap, "/usr/bin/python3": False}
    # Fixed host imports only, isolated from checkout and caller Python paths.
    probe = """import importlib, json
result = {}
for name in ("pcbnew", "wx"):
    try:
        module = importlib.import_module(name)
        result[name] = True
        if name == "pcbnew":
            result["KiCad 9"] = module.GetBuildVersion().startswith("9.")
    except Exception:
        result[name] = False
print(json.dumps(result))
"""
    try:
        result = subprocess.run(
            ["/usr/bin/python3", "-I", "-B", "-c", probe], cwd="/", timeout=15,
            capture_output=True, text=True, check=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        capabilities.update(json.loads(result.stdout))
        capabilities["/usr/bin/python3"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        capabilities["probe_error"] = str(exc)[-500:]
    return capabilities


def trial_proposed_adapter(adapter_id: str, checkout: Path, board: Path, out: Path) -> dict[str, Any]:
    """Explicit CLI-only trial; never called by pipeline/router or registry hooks."""
    spec = PROPOSED_ADAPTERS.get(adapter_id)
    if spec is None:
        raise SignalEvaluationError("unknown proposed adapter")
    if spec["status"] == "proposed_blocked":
        raise SignalEvaluationError("proposal blocked: " + "; ".join(spec["blockers"]))
    if adapter_id != IBOM or spec["status"] != "proposed_pending_human_approval":
        raise SignalEvaluationError("unsupported proposal trial")
    checkout, board = Path(checkout).resolve(), Path(board).resolve()
    original_out = Path(out)
    out = original_out.resolve()
    _verify_checkout(checkout, spec)
    if board.suffix != ".kicad_pcb" or not board.is_file() or board.stat().st_size > 12 * 1024 * 1024:
        raise SignalEvaluationError("trial requires a KiCad PCB under 12 MiB")
    if (original_out.is_symlink() or out.is_relative_to(checkout)
            or checkout.is_relative_to(out) or board.is_relative_to(out)
            or (out.exists() and (not out.is_dir() or any(out.iterdir())))):
        raise SignalEvaluationError("trial output must be an empty, separate directory")
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise SignalEvaluationError("bubblewrap required; refusing unsandboxed trial")
    if Path(bwrap).resolve().is_relative_to(checkout):
        raise SignalEvaluationError("bubblewrap must not come from proposed checkout")
    capabilities = _host_capabilities(bwrap)
    if not all(capabilities.get(name) for name in spec["required_host_capabilities"]):
        raise SignalEvaluationError("required host capabilities unavailable: " + json.dumps(capabilities))
    argv = [x.format(checkout=checkout, board=board, out=out) for x in spec["argv_template"]]
    argv[0] = bwrap
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": "hardware_splicer.github_signal_proposal_trial.v1",
        "adapter_id": adapter_id, "repository": spec["repository"],
        "proposed_commit": spec["proposed_commit"], "license_claim": spec["license_claim"],
        "approval_effect": "none", "host_capabilities": capabilities, "argv": argv,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "input_sha256": sha256_file(board), "output_sha256": None,
    }
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, errors="replace", timeout=120, check=False,
            cwd="/", env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        record.update(exit_code=result.returncode, stderr_tail=(result.stderr or "")[-2000:])
    except (OSError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        record.update(exit_code=None, stderr_tail=stderr[-2000:], execution_error=str(exc))
    record["elapsed_seconds"] = time.monotonic() - start
    artifact = out / "ibom.html"
    record["output_check"] = check_ibom_output(board, artifact)
    if artifact.exists() and not artifact.is_symlink() and stat.S_ISREG(artifact.stat().st_mode):
        record["output_sha256"] = sha256_file(artifact)
    try:
        _verify_checkout(checkout, spec)
        record["checkout_clean_after"] = True
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        record.update(checkout_clean_after=False, checkout_error=str(exc))
    record["input_unchanged"] = sha256_file(board) == record["input_sha256"]
    record["ok"] = (record["exit_code"] == 0 and record["output_check"]["ok"]
                    and record["checkout_clean_after"] and record["input_unchanged"])
    # Exclusive creation also rejects a symlink planted by the trialled tool.
    with (out / TRIAL_FILENAME).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record
