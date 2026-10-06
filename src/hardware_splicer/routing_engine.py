"""Capability-gated autoroute engine.

Routing produces candidate PCB text for review. It never writes into a project,
never touches a revision, and never treats a routed board as verified. DRC
results, if attached later, are evidence — not approval. Authority is never
implicitly upgraded.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .bounded_process import wait_leader_and_kill_group
from .build_files_security import max_kicad_content_bytes
from .kicad_diff import _tokenize_sexp, diff_kicad_text, parse_kicad_sexp

PROBE_TTL_S = 60.0
LOG_TAIL_BYTES = 2048
_GRAPHIC_ATOMS = frozenset(
    {
        "gr_line",
        "gr_text",
        "gr_rect",
        "gr_circle",
        "gr_arc",
        "gr_poly",
        "gr_curve",
        "dimension",
        "image",
    }
)
_ROUTING_ALLOWED_HEADS = frozenset(
    {
        "segment",
        "via",
        "zone",
        "footprint",
        "generator",
        "generator_version",
        "version",
        "uuid",
    }
)
HELPERS_DIR = Path(__file__).resolve().parent / "_pcbnew_helpers"
EXPORT_DSN_HELPER = HELPERS_DIR / "export_dsn.py"
IMPORT_SES_HELPER = HELPERS_DIR / "import_ses.py"
CANDIDATE_WARNING = "routed output is a candidate, not a DRC-clean or fab-ready board"

_probe_cache: dict[str, Any] | None = None
_probe_cached_at = 0.0


class RoutingUnavailable(RuntimeError):
    """Required routing tools are missing. Message is short on purpose."""


class RoutingError(RuntimeError):
    """Routing failed. Message is short and never includes board text."""


class RoutingEngine(Protocol):
    """Injectable router. Tests supply fakes; production uses FreeRoutingEngine."""

    def route(
        self,
        pcb_text: str,
        *,
        timeout_s: float,
        max_passes: int,
        keep_existing_tracks: bool,
    ) -> str | EngineOutput: ...


@dataclass
class EngineOutput:
    text: str
    log: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class RoutingResult:
    text: str
    engine: str
    stats: dict[str, Any]
    diff: dict[str, Any]
    warnings: list[str]
    log_tail: str


def reset_capability_cache() -> None:
    global _probe_cache, _probe_cached_at
    _probe_cache = None
    _probe_cached_at = 0.0


def capability_probe() -> dict[str, Any]:
    """Report whether FreeRouting can run. Cached for 60 seconds."""

    global _probe_cache, _probe_cached_at
    now = time.monotonic()
    if _probe_cache is not None and (now - _probe_cached_at) < PROBE_TTL_S:
        return _probe_cache
    result = _probe_now()
    _probe_cache = result
    _probe_cached_at = now
    return result


def resolve_kicad_python() -> str | None:
    probe = capability_probe()
    component = probe["components"]["kicad_python"]
    if component.get("ok") and component.get("path"):
        return str(component["path"])
    return None


def route_pcb(
    pcb_text: str,
    *,
    engine: RoutingEngine | None = None,
    timeout_s: float = 300,
    max_passes: int = 20,
    keep_existing_tracks: bool = False,
) -> RoutingResult:
    """Route PCB text into a reviewable candidate. Never writes a project."""

    if not isinstance(pcb_text, str):
        raise RoutingError("invalid KiCad PCB text")
    if len(pcb_text.encode("utf-8")) > max_kicad_content_bytes():
        raise RoutingError("input exceeds size limit")
    _require_pcb_text(pcb_text)

    if engine is None:
        probe = capability_probe()
        if not probe["available"]:
            raise RoutingUnavailable(probe["reason"] or "routing unavailable")
        engine = FreeRoutingEngine()

    raw = engine.route(
        pcb_text,
        timeout_s=timeout_s,
        max_passes=max_passes,
        keep_existing_tracks=keep_existing_tracks,
    )
    output = raw if isinstance(raw, EngineOutput) else EngineOutput(text=raw)
    routed = output.text
    if not isinstance(routed, str):
        raise RoutingError("engine returned no PCB text")
    if len(routed.encode("utf-8")) > max_kicad_content_bytes():
        raise RoutingError("output exceeds size limit")
    _require_pcb_text(routed)
    _assert_placement_and_tracks(pcb_text, routed, keep_existing_tracks=keep_existing_tracks)

    report = diff_kicad_text("pcb", pcb_text, routed)
    before = _pcb_counts(pcb_text)
    after = _pcb_counts(routed)
    warnings = list(output.warnings)
    if CANDIDATE_WARNING not in warnings:
        warnings.append(CANDIDATE_WARNING)
    engine_name = str(getattr(engine, "name", None) or engine.__class__.__name__)
    return RoutingResult(
        text=routed,
        engine=engine_name,
        stats={
            "nets_total": after["nets_total"],
            "nets_routed_before": before["nets_routed"],
            "nets_routed_after": after["nets_routed"],
            "segments_before": before["segments"],
            "segments_after": after["segments"],
            "vias_before": before["vias"],
            "vias_after": after["vias"],
        },
        diff={
            "summary": report["summary"],
            "changes": report["changes"][:50],
        },
        warnings=warnings,
        log_tail=_tail_bytes(output.log, LOG_TAIL_BYTES),
    )


class FreeRoutingEngine:
    """DSN export → FreeRouting jar → SES import, all via subprocesses."""

    name = "freerouting"

    def route(
        self,
        pcb_text: str,
        *,
        timeout_s: float,
        max_passes: int,
        keep_existing_tracks: bool,
    ) -> EngineOutput:
        del keep_existing_tracks  # enforced by route_pcb after import
        python = _require_kicad_python()
        java = _require_java()
        jar = _require_jar()
        de_flag = os.environ.get("HARDWARE_SPLICER_FREEROUTING_DE_FLAG", "-de")
        do_flag = os.environ.get("HARDWARE_SPLICER_FREEROUTING_DO_FLAG", "-do")
        mp_flag = os.environ.get("HARDWARE_SPLICER_FREEROUTING_MP_FLAG", "-mp")
        work = Path(tempfile.mkdtemp(prefix="hs-route-"))
        os.chmod(work, 0o700)
        log_parts: list[str] = []
        deadline = time.monotonic() + max(0.1, float(timeout_s))
        try:
            board_path = work / "board.kicad_pcb"
            dsn_path = work / "board.dsn"
            ses_path = work / "board.ses"
            routed_path = work / "routed.kicad_pcb"
            board_path.write_text(pcb_text, encoding="utf-8")
            env = _minimal_env(work)
            export = _run_process(
                [python, str(EXPORT_DSN_HELPER), str(board_path), str(dsn_path)],
                cwd=work,
                env=env,
                timeout_s=_remaining(deadline),
            )
            log_parts.append(export.log)
            if export.timed_out:
                raise RoutingError("routing timed out")
            if export.returncode != 0 or not dsn_path.is_file() or dsn_path.stat().st_size < 1:
                raise RoutingError("DSN export failed")
            java_cmd = [
                java,
                "-jar",
                str(jar),
                de_flag,
                str(dsn_path),
                do_flag,
                str(ses_path),
                mp_flag,
                str(int(max_passes)),
            ]
            routed_run = _run_process(java_cmd, cwd=work, env=env, timeout_s=_remaining(deadline))
            log_parts.append(routed_run.log)
            if routed_run.timed_out:
                raise RoutingError("routing timed out")
            if routed_run.returncode != 0:
                raise RoutingError(f"java exited with code {routed_run.returncode}")
            if not ses_path.is_file():
                raise RoutingError("missing SES")
            if ses_path.stat().st_size > max_kicad_content_bytes():
                raise RoutingError("output exceeds size limit")
            imported = _run_process(
                [
                    python,
                    str(IMPORT_SES_HELPER),
                    str(board_path),
                    str(ses_path),
                    str(routed_path),
                ],
                cwd=work,
                env=env,
                timeout_s=_remaining(deadline),
            )
            log_parts.append(imported.log)
            if imported.timed_out:
                raise RoutingError("routing timed out")
            if imported.returncode != 0 or not routed_path.is_file():
                raise RoutingError("SES import failed")
            if routed_path.stat().st_size > max_kicad_content_bytes():
                raise RoutingError("output exceeds size limit")
            text = routed_path.read_text(encoding="utf-8", errors="replace")
            return EngineOutput(text=text, log="\n".join(part for part in log_parts if part))
        finally:
            shutil.rmtree(work, ignore_errors=True)


@dataclass
class _ProcResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool

    @property
    def log(self) -> str:
        parts = [part for part in (self.stdout, self.stderr) if part]
        return "\n".join(parts)


def _probe_now() -> dict[str, Any]:
    kicad = _probe_kicad_python()
    java = _probe_java()
    jar = _probe_jar()
    reasons: list[str] = []
    if not kicad["ok"]:
        reasons.append("set HARDWARE_SPLICER_KICAD_PYTHON to a Python that can import pcbnew")
    if not java["ok"]:
        reasons.append("install Java or set HARDWARE_SPLICER_JAVA")
    if not jar["ok"]:
        reasons.append("set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar")
    available = not reasons
    return {
        "available": available,
        "reason": None if available else "; ".join(reasons),
        "components": {
            "kicad_python": kicad,
            "java": java,
            "freerouting_jar": jar,
        },
    }


def _probe_kicad_python() -> dict[str, Any]:
    for path in _kicad_python_candidates():
        version = _pcbnew_version(path)
        if version is not None:
            return {"ok": True, "version": version, "path": path}
    env = os.environ.get("HARDWARE_SPLICER_KICAD_PYTHON", "").strip()
    return {"ok": False, "version": None, "path": env or None}


def _kicad_python_candidates() -> list[str]:
    env = os.environ.get("HARDWARE_SPLICER_KICAD_PYTHON", "").strip()
    if env:
        return [env]
    found: list[str] = []
    for path in ("/usr/bin/python3", shutil.which("python3"), shutil.which("python")):
        if path and path not in found and Path(path).is_file():
            found.append(path)
    return found


def _pcbnew_version(python: str) -> str | None:
    if not python or not Path(python).is_file() or not os.access(python, os.X_OK):
        return None
    try:
        result = _run_process(
            [python, "-c", "import pcbnew; print(pcbnew.Version())"],
            cwd=Path("/tmp"),
            env=_minimal_env(Path("/tmp")),
            timeout_s=20,
        )
    except (RoutingError, RoutingUnavailable):
        return None
    if result.timed_out or result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else "unknown"


def _probe_java() -> dict[str, Any]:
    java = _java_binary()
    if not java or not Path(java).is_file() or not os.access(java, os.X_OK):
        return {"ok": False, "version": None}
    try:
        result = _run_process(
            [java, "-version"],
            cwd=Path("/tmp"),
            env=_minimal_env(Path("/tmp")),
            timeout_s=15,
        )
    except (RoutingError, RoutingUnavailable):
        return {"ok": False, "version": None}
    if result.timed_out:
        return {"ok": False, "version": None}
    # `java -version` writes to stderr; we fold both streams into log.
    version = _parse_java_version(result.log)
    if result.returncode != 0 and version is None:
        return {"ok": False, "version": None}
    return {"ok": True, "version": version or "unknown"}


def _java_binary() -> str | None:
    env = os.environ.get("HARDWARE_SPLICER_JAVA", "").strip()
    if env:
        return env
    return shutil.which("java")


def _parse_java_version(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if "version" in stripped.lower():
            if '"' in stripped:
                return stripped.split('"')[1]
            return stripped
    return None


def _probe_jar() -> dict[str, Any]:
    raw = os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR", "").strip()
    if not raw:
        return {"ok": False, "path": None, "sha256_prefix": None}
    path = Path(raw)
    if not path.is_file():
        return {"ok": False, "path": str(path), "sha256_prefix": None}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"ok": True, "path": str(path), "sha256_prefix": digest.hexdigest()[:12]}


def _require_kicad_python() -> str:
    path = None
    component = _probe_kicad_python()
    if component.get("ok"):
        path = component.get("path")
    if not path:
        raise RoutingUnavailable("set HARDWARE_SPLICER_KICAD_PYTHON to a Python that can import pcbnew")
    return str(path)


def _require_java() -> str:
    java = _java_binary()
    if not java or not Path(java).is_file() or not os.access(java, os.X_OK):
        raise RoutingUnavailable("install Java or set HARDWARE_SPLICER_JAVA")
    return java


def _require_jar() -> Path:
    raw = os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR", "").strip()
    if not raw or not Path(raw).is_file():
        raise RoutingUnavailable("set HARDWARE_SPLICER_FREEROUTING_JAR to a FreeRouting jar")
    return Path(raw)


def _require_pcb_text(text: str) -> None:
    try:
        _tokenize_sexp(text)
        tree = parse_kicad_sexp(text)
    except Exception:
        raise RoutingError("invalid KiCad PCB text") from None
    if not tree or tree[0] != "kicad_pcb":
        raise RoutingError("invalid KiCad PCB text")


def _assert_placement_and_tracks(before: str, after: str, *, keep_existing_tracks: bool) -> None:
    before_tree = parse_kicad_sexp(before)
    after_tree = parse_kicad_sexp(after)
    _assert_non_routing_toplevel_identical(before_tree, after_tree)
    _assert_footprints_identical(before_tree, after_tree)
    _assert_zone_identity_identical(before_tree, after_tree)
    if _net_table(before_tree) != _net_table(after_tree):
        raise RoutingError("routing changed more than copper tracks: net")
    extra = _first_graphic_change(before_tree, after_tree)
    if extra is not None:
        raise RoutingError(f"routing changed more than copper tracks: {extra}")

    report = diff_kicad_text("pcb", before, after)
    for change in report["changes"]:
        item_type = str(change.get("item_type") or "item")
        kind = change.get("change")
        if item_type == "footprint":
            raise RoutingError("routing changed placement")
        if item_type == "zone":
            continue
        if item_type in {"segment", "via"}:
            if kind == "added":
                continue
            if kind == "removed":
                if keep_existing_tracks:
                    raise RoutingError("routing removed existing tracks")
                continue
            raise RoutingError(f"routing changed more than copper tracks: {item_type}")
        raise RoutingError(f"routing changed more than copper tracks: {item_type}")


def _named_child(node: list[Any], name: str) -> list[Any] | None:
    for item in node[1:]:
        if isinstance(item, list) and item and item[0] == name:
            return item
    return None


def _child_atom(node: list[Any], name: str) -> str | None:
    child = _named_child(node, name)
    if child is None or len(child) < 2 or isinstance(child[1], list):
        return None
    return str(child[1])


def _canonical_tokens(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        parts: list[str] = ["("]
        for item in value:
            parts.extend(_canonical_tokens(item))
        parts.append(")")
        return tuple(parts)
    return (str(value),)


def _footprint_uuid(node: list[Any]) -> str | None:
    return _child_atom(node, "uuid") or _child_atom(node, "tstamp")


def _top_level_nodes(tree: list[Any], *names: str) -> list[list[Any]]:
    wanted = set(names)
    rows: list[list[Any]] = []
    for node in tree[1:]:
        if isinstance(node, list) and node and node[0] in wanted:
            rows.append(node)
    return rows


def _non_routing_toplevel_groups(tree: list[Any]) -> dict[str, list[tuple[str, ...]]]:
    groups: dict[str, list[tuple[str, ...]]] = {}
    for node in tree[1:]:
        if not isinstance(node, list) or not node or not isinstance(node[0], str):
            continue
        head = node[0]
        if head in _ROUTING_ALLOWED_HEADS:
            continue
        groups.setdefault(head, []).append(_canonical_tokens(node))
    return groups


def _assert_non_routing_toplevel_identical(before: list[Any], after: list[Any]) -> None:
    before_groups = _non_routing_toplevel_groups(before)
    after_groups = _non_routing_toplevel_groups(after)
    for head in sorted(set(before_groups) | set(after_groups)):
        if Counter(before_groups.get(head, ())) != Counter(after_groups.get(head, ())):
            raise RoutingError(f"routing changed more than copper tracks: {head}")


def _partition_uuid_nodes(
    nodes: list[list[Any]], uuid_fn: Callable[[list[Any]], str | None]
) -> tuple[dict[str, list[list[Any]]], list[list[Any]]]:
    by_uuid: dict[str, list[Any]] = {}
    bare: list[list[Any]] = []
    for node in nodes:
        uid = uuid_fn(node)
        if uid:
            by_uuid.setdefault(uid, []).append(node)
        else:
            bare.append(node)
    return by_uuid, bare


def _assert_uuid_or_counter_identical(
    before_nodes: list[list[Any]],
    after_nodes: list[list[Any]],
    uuid_fn: Callable[[list[Any]], str | None],
    tokens_fn: Callable[[list[Any]], tuple[str, ...]],
    error: str,
) -> None:
    before_map, before_bare = _partition_uuid_nodes(before_nodes, uuid_fn)
    after_map, after_bare = _partition_uuid_nodes(after_nodes, uuid_fn)
    if any(len(group) != 1 for group in before_map.values()) or any(
        len(group) != 1 for group in after_map.values()
    ):
        raise RoutingError(error)
    if set(before_map) != set(after_map):
        raise RoutingError(error)
    for uid, before_node in before_map.items():
        if tokens_fn(before_node[0]) != tokens_fn(after_map[uid][0]):
            raise RoutingError(error)
    if Counter(tokens_fn(node) for node in before_bare) != Counter(
        tokens_fn(node) for node in after_bare
    ):
        raise RoutingError(error)


def _assert_footprints_identical(before: list[Any], after: list[Any]) -> None:
    _assert_uuid_or_counter_identical(
        _top_level_nodes(before, "footprint", "module"),
        _top_level_nodes(after, "footprint", "module"),
        _footprint_uuid,
        _canonical_tokens,
        "routing changed placement",
    )


_ZONE_FILL_CHILDREN = frozenset({"filled_polygon", "fill_segments"})


def _zone_uuid(node: list[Any]) -> str | None:
    return _child_atom(node, "uuid") or _child_atom(node, "tstamp")


def _zone_without_fill_geometry(node: list[Any]) -> list[Any]:
    return [
        node[0],
        *[
            child
            for child in node[1:]
            if not (isinstance(child, list) and child and child[0] in _ZONE_FILL_CHILDREN)
        ],
    ]


def _zone_identity_tokens(node: list[Any]) -> tuple[str, ...]:
    return _canonical_tokens(_zone_without_fill_geometry(node))


def _assert_zone_identity_identical(before: list[Any], after: list[Any]) -> None:
    _assert_uuid_or_counter_identical(
        _top_level_nodes(before, "zone"),
        _top_level_nodes(after, "zone"),
        _zone_uuid,
        _zone_identity_tokens,
        "routing changed more than copper tracks: zone",
    )


def _net_table(tree: list[Any]) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for node in tree[1:]:
        if isinstance(node, list) and node and node[0] == "net":
            rows.append(tuple(str(part) for part in node[1:] if not isinstance(part, list)))
    return rows


def _graphics(tree: list[Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for node in tree[1:]:
        if isinstance(node, list) and node and isinstance(node[0], str) and node[0] in _GRAPHIC_ATOMS:
            rows.append((node[0], repr(node)))
    return rows


def _first_graphic_change(before: list[Any], after: list[Any]) -> str | None:
    before_rows = _graphics(before)
    after_rows = _graphics(after)
    if before_rows == after_rows:
        return None
    before_types = Counter(name for name, _payload in before_rows)
    after_types = Counter(name for name, _payload in after_rows)
    for name in sorted(set(before_types) | set(after_types)):
        if before_types[name] != after_types[name]:
            return name
    before_set = set(before_rows)
    after_set = set(after_rows)
    for name, payload in after_rows:
        if (name, payload) not in before_set:
            return name
    for name, payload in before_rows:
        if (name, payload) not in after_set:
            return name
    return "graphic"


def _pcb_counts(text: str) -> dict[str, int]:
    tree = parse_kicad_sexp(text)
    nets_total = 0
    routed: set[str] = set()
    segments = 0
    vias = 0
    for node in tree[1:]:
        if not isinstance(node, list) or not node:
            continue
        name = node[0]
        if name == "net":
            nets_total += 1
        elif name == "segment":
            segments += 1
            net = _child_net(node)
            if net is not None:
                routed.add(net)
        elif name == "via":
            vias += 1
            net = _child_net(node)
            if net is not None:
                routed.add(net)
    return {
        "nets_total": nets_total,
        "nets_routed": len(routed),
        "segments": segments,
        "vias": vias,
    }


def _child_net(node: list[Any]) -> str | None:
    for item in node[1:]:
        if isinstance(item, list) and item and item[0] == "net" and len(item) > 1:
            return str(item[1])
    return None


def _minimal_env(home: Path) -> dict[str, str]:
    path = os.environ.get("PATH") or "/usr/bin:/bin"
    return {"PATH": path, "HOME": str(home)}


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise RoutingError("routing timed out")
    return left


def _tail_bytes(text: str, limit: int) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[-limit:].decode("utf-8", errors="ignore")


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
) -> _ProcResult:
    process: subprocess.Popen[bytes] | None = None
    timed_out = False
    try:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                bufsize=0,
            )
        except (FileNotFoundError, PermissionError):
            raise RoutingUnavailable("executable missing or not executable") from None
        except OSError:
            raise RoutingError("failed to launch process") from None

        stdout_buf = _ByteTail(LOG_TAIL_BYTES)
        stderr_buf = _ByteTail(LOG_TAIL_BYTES)
        reader_out = threading.Thread(
            target=_read_stream, args=(process.stdout, stdout_buf), daemon=True
        )
        reader_err = threading.Thread(
            target=_read_stream, args=(process.stderr, stderr_buf), daemon=True
        )
        reader_out.start()
        reader_err.start()
        # Kills the whole group once the leader is gone or out of time, so a descendant that outlives the leader is not
        # left running and does not keep the readers waiting.
        timed_out = wait_leader_and_kill_group(process, max(0.1, float(timeout_s)))
        reader_out.join(timeout=2)
        reader_err.join(timeout=2)
        return _ProcResult(
            returncode=int(process.returncode if process.returncode is not None else 0),
            stdout=stdout_buf.text(),
            stderr=stderr_buf.text(),
            timed_out=timed_out,
        )
    except (RoutingError, RoutingUnavailable):
        if process is not None:
            _kill_group(process)
            _reap(process)
        raise
    except BaseException:
        if process is not None:
            _kill_group(process)
            _reap(process)
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                _kill_group(process)
            _reap(process)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass


class _ByteTail:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._data = bytearray()
        self._lock = threading.Lock()

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return
        with self._lock:
            self._data.extend(chunk)
            overflow = len(self._data) - self.limit
            if overflow > 0:
                del self._data[:overflow]

    def text(self) -> str:
        with self._lock:
            return bytes(self._data).decode("utf-8", errors="replace")


def _read_stream(stream: Any, buf: _ByteTail) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            buf.append(chunk)
    except (ValueError, OSError):
        return


def _reap(process: subprocess.Popen[bytes]) -> None:
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            pass
    except OSError:
        pass


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except OSError:
            pass
