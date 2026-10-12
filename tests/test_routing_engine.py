"""Capability-gated autoroute engine."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Iterator
from pathlib import Path

import pytest

from hardware_splicer.kicad_diff import _tokenize_sexp, diff_kicad_text
from hardware_splicer import routing_engine as routing_engine_mod
from hardware_splicer.routing_engine import (
    CANDIDATE_WARNING,
    EXPORT_DSN_HELPER,
    IMPORT_SES_HELPER,
    RoutingEngine,
    RoutingError,
    RoutingUnavailable,
    _run_process,
    capability_probe,
    reset_capability_cache,
    resolve_kicad_python,
    route_pcb,
)

REPO = Path(__file__).resolve().parents[1]
SPI_PCB = (
    REPO
    / "hardware"
    / "reference_designs"
    / "spi_flash_adapter_v1"
    / "spi_flash_adapter_v1.kicad_pcb"
)

MINIMAL_PCB = """(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (2 "B.Cu" signal)
  )
  (general
    (thickness 1.6)
  )
  (paper "A4")
  (title_block
    (title "board")
  )
  (setup
    (pad_to_mask_clearance 0)
  )
  (net 0 "")
  (net 1 "N1")
  (net 2 "N2")
  (footprint "Resistor_SMD:R_0603_1608Metric"
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
    (at 10 10)
    (property "Reference" "R1"
      (at 0 -1.43 0)
      (layer "F.SilkS")
    )
    (property "Value" "1k"
      (at 0 1.43 0)
      (layer "F.Fab")
    )
    (fp_line
      (start 0 0)
      (end 1 0)
      (layer "F.SilkS")
      (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa30")
    )
    (fp_text user "MARK"
      (at 0 0 0)
      (layer "F.Fab")
      (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa31")
    )
    (pad "1" smd rect
      (at -0.8 0)
      (size 0.8 0.95)
      (layers "F.Cu" "F.Mask")
      (net 1 "N1")
      (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa32")
    )
  )
  (footprint "Resistor_SMD:R_0603_1608Metric"
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
    (at 20 10)
    (property "Reference" "R2"
      (at 0 -1.43 0)
      (layer "F.SilkS")
    )
    (property "Value" "1k"
      (at 0 1.43 0)
      (layer "F.Fab")
    )
  )
  (segment
    (start 10 10)
    (end 20 10)
    (width 0.2)
    (layer "F.Cu")
    (net 1)
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
  )
)
"""

ADDED_SEGMENT = """  (segment
    (start 10 12)
    (end 20 12)
    (width 0.2)
    (layer "F.Cu")
    (net 2)
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")
  )
"""

ADDED_VIA = """  (via
    (at 15 10)
    (size 0.6)
    (drill 0.3)
    (layers "F.Cu" "B.Cu")
    (net 1)
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5")
  )
"""

ZONE_BLOCK = """  (zone
    (net 1)
    (net_name "N1")
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa10")
    (polygon
      (pts
        (xy 0 0)
        (xy 8 0)
        (xy 8 8)
        (xy 0 8)
      )
    )
  )
"""

GRAPHIC_LINE = """  (gr_line
    (start 0 0)
    (end 1 1)
    (stroke
      (width 0.15)
      (type default)
    )
    (layer "Dwgs.User")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa20")
  )
"""

ZONE_FILL_BLOCK = """  (zone
    (net 1)
    (net_name "N1")
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa11")
    (fill yes
      (thermal_gap 0.5)
      (thermal_bridge_width 0.5)
    )
    (polygon
      (pts
        (xy 0 0)
        (xy 8 0)
        (xy 8 8)
        (xy 0 8)
      )
    )
    (filled_polygon
      (layer "F.Cu")
      (pts
        (xy 0.2 0.2)
        (xy 7.8 0.2)
        (xy 7.8 7.8)
        (xy 0.2 7.8)
      )
    )
  )
"""

PCB_WITH_ZONE = MINIMAL_PCB[: MINIMAL_PCB.rfind(")")] + ZONE_BLOCK + MINIMAL_PCB[MINIMAL_PCB.rfind(")") :]
PCB_WITH_ZONE_FILL = MINIMAL_PCB[: MINIMAL_PCB.rfind(")")] + ZONE_FILL_BLOCK + MINIMAL_PCB[MINIMAL_PCB.rfind(")") :]

UUIDLESS_FOOTPRINT_A = """  (footprint "Lib:FP"
    (layer "F.Cu")
    (at 10 10)
    (property "Reference" "R1"
      (at 0 0 0)
    )
    (fp_text user "FIRST"
      (at 0 0 0)
      (layer "F.Fab")
    )
  )
"""
UUIDLESS_FOOTPRINT_B = UUIDLESS_FOOTPRINT_A.replace("FIRST", "SECOND")
PCB_UUIDLESS_FOOTPRINTS = """(kicad_pcb
  (version 20241229)
  (generator "pcbnew")
  (layers
    (0 "F.Cu" signal)
    (2 "B.Cu" signal)
  )
  (net 0 "")
""" + UUIDLESS_FOOTPRINT_A + UUIDLESS_FOOTPRINT_B + ")\n"

UUIDLESS_ZONE_A = """  (zone
    (net 1)
    (net_name "N1")
    (layer "F.Cu")
    (polygon
      (pts
        (xy 0 0)
        (xy 4 0)
        (xy 4 4)
        (xy 0 4)
      )
    )
  )
"""
PCB_UUIDLESS_ZONES = MINIMAL_PCB[: MINIMAL_PCB.rfind(")")] + UUIDLESS_ZONE_A + UUIDLESS_ZONE_A + MINIMAL_PCB[MINIMAL_PCB.rfind(")") :]

# Specctra session with an empty routes/network_out section. pcbnew 9.0.2
# accepts this shape; a bare `(routes)` list returns False.
EMPTY_SES = """(session "board.ses"
  (base_design "board.dsn")
  (placement)
  (was_is)
  (routes
    (resolution um 10)
    (library_out)
    (network_out)
  )
)
"""

_TWO_NET_GENERATOR = r"""
import pcbnew
import sys

lib = "/usr/share/kicad/footprints/Resistor_SMD.pretty"
name = "R_0603_1608Metric"
board = pcbnew.CreateEmptyBoard()

def add_fp(ref, x, y):
    fp = pcbnew.FootprintLoad(lib, name)
    fp.SetReference(ref)
    fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    board.Add(fp)
    return fp

r1 = add_fp("R1", 10, 10)
r2 = add_fp("R2", 20, 10)
net_a = pcbnew.NETINFO_ITEM(board, "N1")
net_b = pcbnew.NETINFO_ITEM(board, "N2")
board.Add(net_a)
board.Add(net_b)
pads1 = list(r1.Pads())
pads2 = list(r2.Pads())
pads1[0].SetNet(net_a)
pads2[0].SetNet(net_a)
pads1[1].SetNet(net_b)
pads2[1].SetNet(net_b)

def rect(x1, y1, x2, y2):
    for a, b in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
        shape.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(b[0]), pcbnew.FromMM(b[1])))
        board.Add(shape)

rect(0, 0, 40, 20)
pcbnew.SaveBoard(sys.argv[1], board)
"""


@pytest.fixture(autouse=True)
def _reset_probe_cache() -> Iterator[None]:
    reset_capability_cache()
    yield
    reset_capability_cache()


def _write_executable(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _fake_java_script(*, body: str) -> str:
    return textwrap.dedent(
        f"""\
        #!{sys.executable}
        import sys
        from pathlib import Path

        args = sys.argv[1:]
        if "-do" not in args:
            print('openjdk version "21.0.0"', file=sys.stderr)
            raise SystemExit(0)

        def opt(flag: str) -> str:
            return args[args.index(flag) + 1]

        ses = Path(opt("-do"))
        """
    ) + textwrap.dedent(body)


def _kicad_python_or_skip() -> str:
    reset_capability_cache()
    path = resolve_kicad_python()
    if not path:
        pytest.skip("KiCad python with pcbnew is missing")
    return path


def _footprint_changes(before: str, after: str) -> list[dict]:
    report = diff_kicad_text("pcb", before, after)
    return [row for row in report["changes"] if row["item_type"] == "footprint"]


class _AddTrackEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return _insert_before_close(pcb_text, ADDED_SEGMENT)


class _RemoveTrackEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        marker = '(uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")'
        start = pcb_text.rfind("(segment", 0, pcb_text.find(marker))
        end = pcb_text.find(")", pcb_text.find(marker)) + 1
        end = pcb_text.find(")", end) + 1
        return pcb_text[:start] + pcb_text[end:]


class _MoveFootprintEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(at 10 10)", "(at 99 99)", 1)


class _IdentityEngine:
    name = "identity"

    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text


def _insert_before_close(pcb_text: str, block: str) -> str:
    closing = pcb_text.rfind(")")
    return pcb_text[:closing] + block + pcb_text[closing:]


class _AddSegmentAndViaEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return _insert_before_close(pcb_text, ADDED_SEGMENT + ADDED_VIA)


class _ChangeNetTableEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(net 2 "N2")', '(net 2 "N2")\n  (net 3 "N3")', 1)


class _RenameNetEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(net 1 "N1")', '(net 1 "SIG")', 1)


class _DeleteZoneEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(ZONE_BLOCK, "", 1)


class _MoveZoneOutlineEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(xy 8 8)", "(xy 9 9)", 1)


class _AddGraphicLineEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return _insert_before_close(pcb_text, GRAPHIC_LINE)


PAD_NET_BEFORE = """    (pad "1" smd rect
      (at -0.8 0)
      (size 0.8 0.95)
      (layers "F.Cu" "F.Mask")
      (net 1 "N1")
      (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa32")
    )"""
PAD_NET_AFTER = PAD_NET_BEFORE.replace('(net 1 "N1")', '(net 2 "N2")', 1)
FP_LINE_BLOCK = """    (fp_line
      (start 0 0)
      (end 1 0)
      (layer "F.SilkS")
      (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa30")
    )
"""


class _ChangePadNetEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(PAD_NET_BEFORE, PAD_NET_AFTER, 1)


class _ChangePadSizeEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(size 0.8 0.95)", "(size 1.2 1.2)", 1)


class _EditFpTextEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(fp_text user "MARK"', '(fp_text user "EDITED"', 1)


class _DeleteFpLineEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(FP_LINE_BLOCK, "", 1)


class _FootprintWhitespaceEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(
            '(fp_text user "MARK"\n      (at 0 0 0)',
            '(fp_text user "MARK"\n\n      (at  0   0  0)',
            1,
        )


class _ChangeThermalGapEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(thermal_gap 0.5)", "(thermal_gap 0.8)", 1)


class _ChangeZoneNetEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(
            """  (zone
    (net 1)
    (net_name "N1")
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa11")""",
            """  (zone
    (net 2)
    (net_name "N2")
    (layer "F.Cu")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa11")""",
            1,
        )


class _ChangeZoneLayerEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(
            '(net_name "N1")\n    (layer "F.Cu")\n    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa11")',
            '(net_name "N1")\n    (layer "B.Cu")\n    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa11")',
            1,
        )


class _RefillZoneEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(xy 0.2 0.2)", "(xy 0.3 0.3)", 1)


class _EditLayerNameEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(0 "F.Cu" signal)', '(0 "Top.Cu" signal)', 1)


class _EditSetupClearanceEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(pad_to_mask_clearance 0)", "(pad_to_mask_clearance 0.1)", 1)


class _EditTitleBlockEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(title "board")', '(title "other")', 1)


DIMENSION_BLOCK = """  (dimension
    (type aligned)
    (layer "Dwgs.User")
    (uuid "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa40")
    (pts
      (xy 0 0)
      (xy 10 0)
    )
    (height 5)
    (gr_text "10"
      (at 5 5 0)
      (layer "Dwgs.User")
    )
  )
"""


class _AddDimensionEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return _insert_before_close(pcb_text, DIMENSION_BLOCK)


class _AllowedCopperAndGeneratorEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        text = pcb_text.replace("(version 20241229)", "(version 20250101)", 1)
        text = text.replace('(generator "pcbnew")', '(generator "routed")', 1)
        text = text.replace('(generator "routed")', '(generator "routed")\n  (generator_version "9.0.2")', 1)
        text = text.replace("(xy 0.2 0.2)", "(xy 0.3 0.3)", 1)
        return _insert_before_close(text, ADDED_SEGMENT + ADDED_VIA)


class _EditFirstUuidlessFootprintEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace('(fp_text user "FIRST"', '(fp_text user "EDITED"', 1)


class _DeleteFirstUuidlessZoneEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace(UUIDLESS_ZONE_A, "", 1)


class _ReplaceFirstUuidlessZoneEngine:
    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return pcb_text.replace("(xy 0 0)", "(xy 1 1)", 1)


def test_capability_probe_missing_jar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_FREEROUTING_JAR", raising=False)
    probe = capability_probe()
    assert probe["available"] is False
    assert probe["components"]["freerouting_jar"]["ok"] is False
    assert "HARDWARE_SPLICER_FREEROUTING_JAR" in (probe["reason"] or "")
    assert "FreeRouting jar" in (probe["reason"] or "")


def test_capability_probe_missing_java(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(tmp_path / "no-java"))
    (tmp_path / "dummy.jar").write_bytes(b"jar")
    monkeypatch.setenv("HARDWARE_SPLICER_FREEROUTING_JAR", str(tmp_path / "dummy.jar"))
    probe = capability_probe()
    assert probe["components"]["java"]["ok"] is False
    assert probe["available"] is False
    assert "HARDWARE_SPLICER_JAVA" in (probe["reason"] or "") or "Java" in (probe["reason"] or "")


def test_capability_probe_missing_kicad_python(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", str(tmp_path / "no-python"))
    (tmp_path / "dummy.jar").write_bytes(b"jar")
    monkeypatch.setenv("HARDWARE_SPLICER_FREEROUTING_JAR", str(tmp_path / "dummy.jar"))
    probe = capability_probe()
    assert probe["components"]["kicad_python"]["ok"] is False
    assert probe["available"] is False
    assert "HARDWARE_SPLICER_KICAD_PYTHON" in (probe["reason"] or "")
    assert "pcbnew" in (probe["reason"] or "")


def test_capability_probe_jar_sha_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    jar = tmp_path / "fr.jar"
    payload = b"hardware-splicer-freerouting-fixture"
    jar.write_bytes(payload)
    monkeypatch.setenv("HARDWARE_SPLICER_FREEROUTING_JAR", str(jar))
    probe = capability_probe()
    prefix = probe["components"]["freerouting_jar"]["sha256_prefix"]
    expected = hashlib.sha256(payload).hexdigest()
    assert probe["components"]["freerouting_jar"]["ok"] is True
    assert prefix == expected[:12]
    assert expected.startswith(prefix)


def test_capability_probe_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    jar = tmp_path / "fr.jar"
    jar.write_bytes(b"abc")
    monkeypatch.setenv("HARDWARE_SPLICER_FREEROUTING_JAR", str(jar))
    clock = {"t": 1_000.0}
    monkeypatch.setattr(routing_engine_mod.time, "monotonic", lambda: clock["t"])
    first = capability_probe()
    assert first["components"]["freerouting_jar"]["ok"] is True
    jar.unlink()
    second = capability_probe()
    assert second["components"]["freerouting_jar"]["ok"] is True
    clock["t"] += 61.0
    third = capability_probe()
    assert third["components"]["freerouting_jar"]["ok"] is False


def test_route_pcb_refuses_oversize_input() -> None:
    huge = "x" * (16 * 1024 * 1024 + 1)
    with pytest.raises(RoutingError, match="size limit") as caught:
        route_pcb(huge, engine=_IdentityEngine())
    assert huge[:32] not in str(caught.value)


def test_max_pcb_bytes_honors_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARDWARE_SPLICER_MAX_KICAD_CONTENT_BYTES", "64")
    with pytest.raises(RoutingError, match="size limit"):
        route_pcb(MINIMAL_PCB, engine=_IdentityEngine())


def test_route_pcb_unavailable_without_jar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARDWARE_SPLICER_FREEROUTING_JAR", raising=False)
    with pytest.raises(RoutingUnavailable, match="HARDWARE_SPLICER_FREEROUTING_JAR"):
        route_pcb(MINIMAL_PCB)


def test_injected_engine_adds_track_and_reports_diff() -> None:
    result = route_pcb(MINIMAL_PCB, engine=_AddTrackEngine())
    assert result.engine
    assert CANDIDATE_WARNING in result.warnings
    assert result.stats["nets_total"] == 3
    assert result.stats["nets_routed_before"] == 1
    assert result.stats["segments_after"] == result.stats["segments_before"] + 1
    assert result.diff["summary"]["added"] >= 1
    assert len(result.diff["changes"]) <= 50
    _tokenize_sexp(result.text)
    assert _footprint_changes(MINIMAL_PCB, result.text) == []
    assert len(result.log_tail.encode("utf-8")) <= 2048


def test_keep_existing_tracks_false_allows_removal() -> None:
    result = route_pcb(MINIMAL_PCB, engine=_RemoveTrackEngine(), keep_existing_tracks=False)
    assert result.stats["segments_after"] == 0


def test_keep_existing_tracks_true_rejects_removal() -> None:
    with pytest.raises(RoutingError, match="removed existing tracks"):
        route_pcb(MINIMAL_PCB, engine=_RemoveTrackEngine(), keep_existing_tracks=True)


def test_placement_change_raises_routing_error() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(MINIMAL_PCB, engine=_MoveFootprintEngine())


def test_dsn_export_helper_spi_adapter() -> None:
    python = _kicad_python_or_skip()
    if not SPI_PCB.is_file():
        pytest.skip("SPI adapter PCB missing")
    out_dir = Path(os.environ.get("HARDWARE_SPLICER_TMP_ROOT", "/tmp")) / "hs_route_dsn"
    out_dir.mkdir(parents=True, exist_ok=True)
    dsn = out_dir / "board.dsn"
    if dsn.exists():
        dsn.unlink()
    proc = subprocess.run(
        [python, str(EXPORT_DSN_HELPER), str(SPI_PCB), str(dsn)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    text = dsn.read_text(encoding="utf-8", errors="replace")
    assert text.strip()
    assert "(pcb" in text
    assert "(parser" in text
    assert "(network" in text or "(placement" in text


def test_ses_import_helper_empty_session_keeps_footprints(tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    if not SPI_PCB.is_file():
        pytest.skip("SPI adapter PCB missing")
    ses = tmp_path / "board.ses"
    ses.write_text(EMPTY_SES, encoding="utf-8")
    routed = tmp_path / "routed.kicad_pcb"
    proc = subprocess.run(
        [python, str(IMPORT_SES_HELPER), str(SPI_PCB), str(ses), str(routed)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    after = routed.read_text(encoding="utf-8", errors="replace")
    _tokenize_sexp(after)
    before = SPI_PCB.read_text(encoding="utf-8")
    assert _footprint_changes(before, after) == []
    assert after.lstrip().startswith("(kicad_pcb")


def _install_dummy_jar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    jar = tmp_path / "freerouting.jar"
    jar.write_bytes(b"dummy-jar")
    monkeypatch.setenv("HARDWARE_SPLICER_FREEROUTING_JAR", str(jar))
    return jar


def test_pipeline_fake_java_writes_empty_ses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body=f"ses.write_text({EMPTY_SES!r})\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    pcb_text = SPI_PCB.read_text(encoding="utf-8")
    result = route_pcb(pcb_text, timeout_s=60, keep_existing_tracks=False)
    assert result.engine == "freerouting"
    _tokenize_sexp(result.text)
    assert _footprint_changes(pcb_text, result.text) == []
    assert CANDIDATE_WARNING in result.warnings


def test_pipeline_timeout_kills_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    pidfile = tmp_path / "java.pid"
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(
            body=f"""
            import os, time
            Path({str(pidfile)!r}).write_text(str(os.getpid()))
            time.sleep(30)
            """
        ),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    with pytest.raises(RoutingError, match="timed out"):
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=8)
    assert pidfile.is_file()
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_pipeline_nonzero_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body="raise SystemExit(7)\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    with pytest.raises(RoutingError, match="exited with code 7"):
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=30)


def test_pipeline_missing_ses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body="Path(opt('-do')).parent.mkdir(parents=True, exist_ok=True)\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    with pytest.raises(RoutingError, match="missing SES"):
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=30)


def test_pipeline_garbage_ses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body="ses.write_text('this is not a specctra session')\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    with pytest.raises(RoutingError, match="SES import failed"):
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=30)


def test_pipeline_oversize_ses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body="ses.write_bytes(b'x' * (16 * 1024 * 1024 + 8))\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    with pytest.raises(RoutingError, match="size limit"):
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=30)


@pytest.mark.skipif(
    not os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR", "").strip()
    or not Path(os.environ.get("HARDWARE_SPLICER_FREEROUTING_JAR", "")).is_file(),
    reason="HARDWARE_SPLICER_FREEROUTING_JAR is not configured",
)
def test_real_jar_routes_tiny_two_net_board(tmp_path: Path) -> None:
    python = _kicad_python_or_skip()
    dest = tmp_path / "two_net.kicad_pcb"
    built = subprocess.run(
        [python, "-c", _TWO_NET_GENERATOR, str(dest)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if built.returncode != 0 or not dest.is_file():
        pytest.skip(f"could not build two-net board: {built.stderr[-400:]}")
    result = route_pcb(dest.read_text(encoding="utf-8"), timeout_s=120, max_passes=5)
    assert result.engine == "freerouting"
    _tokenize_sexp(result.text)
    assert _footprint_changes(dest.read_text(encoding="utf-8"), result.text) == []
    assert result.stats["nets_total"] >= 2


def test_protocol_accepts_fake_engine() -> None:
    engine: RoutingEngine = _IdentityEngine()
    result = route_pcb(MINIMAL_PCB, engine=engine)
    assert result.text == MINIMAL_PCB
    assert result.engine == "identity"


def test_rejects_net_table_change() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: net"):
        route_pcb(MINIMAL_PCB, engine=_ChangeNetTableEngine())


def test_rejects_deleted_zone() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_WITH_ZONE, engine=_DeleteZoneEngine())


def test_rejects_moved_zone_outline() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_WITH_ZONE, engine=_MoveZoneOutlineEngine())


def test_rejects_renamed_net() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: net"):
        route_pcb(MINIMAL_PCB, engine=_RenameNetEngine())


def test_rejects_added_graphic_line() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: gr_line"):
        route_pcb(MINIMAL_PCB, engine=_AddGraphicLineEngine())


def test_allows_added_segments_and_vias() -> None:
    result = route_pcb(MINIMAL_PCB, engine=_AddSegmentAndViaEngine())
    assert result.stats["segments_after"] == result.stats["segments_before"] + 1
    assert result.stats["vias_after"] == result.stats["vias_before"] + 1
    assert _footprint_changes(MINIMAL_PCB, result.text) == []


def _rss_bytes() -> int:
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


def test_run_process_ring_buffers_huge_output(tmp_path: Path) -> None:
    blaster = tmp_path / "blaster.py"
    blaster.write_text(
        textwrap.dedent(
            """\
            import sys
            chunk = b"Z" * 65536
            for _ in range((200 * 1024 * 1024) // 65536):
                sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.write(b"END_STDOUT_MARKER\\n")
            sys.stdout.buffer.flush()
            """
        ),
        encoding="utf-8",
    )
    tracemalloc.start()
    rss_before = _rss_bytes()
    result = _run_process(
        [sys.executable, str(blaster)],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(tmp_path)},
        timeout_s=30,
    )
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = _rss_bytes()
    assert result.returncode == 0
    assert "END_STDOUT_MARKER" in result.stdout
    assert len(result.stdout.encode("utf-8")) <= 2048
    assert peak < 16 * 1024 * 1024
    assert rss_after - rss_before < 64 * 1024 * 1024


def test_java_removed_after_probe_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python = _kicad_python_or_skip()
    monkeypatch.setenv("HARDWARE_SPLICER_KICAD_PYTHON", python)
    _install_dummy_jar(monkeypatch, tmp_path)
    fake = _write_executable(
        tmp_path / "java",
        _fake_java_script(body=f"ses.write_text({EMPTY_SES!r})\n"),
    )
    monkeypatch.setenv("HARDWARE_SPLICER_JAVA", str(fake))
    reset_capability_cache()
    probe = capability_probe()
    assert probe["components"]["java"]["ok"] is True
    fake.unlink()
    monkeypatch.setattr(routing_engine_mod, "_require_java", lambda: str(fake))
    with pytest.raises(RoutingUnavailable) as caught:
        route_pcb(SPI_PCB.read_text(encoding="utf-8"), timeout_s=30)
    assert not isinstance(caught.value, OSError)
    message = str(caught.value)
    assert "Traceback" not in message


def test_rejects_pad_net_change_inside_footprint() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(MINIMAL_PCB, engine=_ChangePadNetEngine())


def test_rejects_pad_size_change_inside_footprint() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(MINIMAL_PCB, engine=_ChangePadSizeEngine())


def test_rejects_fp_text_edit() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(MINIMAL_PCB, engine=_EditFpTextEngine())


def test_rejects_deleted_fp_line() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(MINIMAL_PCB, engine=_DeleteFpLineEngine())


def test_allows_footprint_whitespace_only_change() -> None:
    result = route_pcb(MINIMAL_PCB, engine=_FootprintWhitespaceEngine())
    assert result.text != MINIMAL_PCB
    assert _footprint_changes(MINIMAL_PCB, result.text) == []


def test_rejects_zone_thermal_gap_change() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_WITH_ZONE_FILL, engine=_ChangeThermalGapEngine())


def test_rejects_zone_net_change() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_WITH_ZONE_FILL, engine=_ChangeZoneNetEngine())


def test_rejects_zone_layer_change() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_WITH_ZONE_FILL, engine=_ChangeZoneLayerEngine())


def test_allows_zone_refill_only() -> None:
    result = route_pcb(PCB_WITH_ZONE_FILL, engine=_RefillZoneEngine())
    assert "(xy 0.3 0.3)" in result.text
    assert _footprint_changes(PCB_WITH_ZONE_FILL, result.text) == []


def test_rejects_edited_layer_name() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: layers"):
        route_pcb(MINIMAL_PCB, engine=_EditLayerNameEngine())


def test_rejects_setup_pad_to_mask_clearance_change() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: setup"):
        route_pcb(MINIMAL_PCB, engine=_EditSetupClearanceEngine())


def test_rejects_title_block_edit() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: title_block"):
        route_pcb(MINIMAL_PCB, engine=_EditTitleBlockEngine())


def test_rejects_added_dimension() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: dimension"):
        route_pcb(MINIMAL_PCB, engine=_AddDimensionEngine())


def test_allows_copper_zone_fill_and_generator_metadata() -> None:
    result = route_pcb(PCB_WITH_ZONE_FILL, engine=_AllowedCopperAndGeneratorEngine())
    assert result.stats["segments_after"] == result.stats["segments_before"] + 1
    assert result.stats["vias_after"] == result.stats["vias_before"] + 1
    assert "(xy 0.3 0.3)" in result.text
    assert '(generator "routed")' in result.text
    assert "(generator_version" in result.text
    assert _footprint_changes(PCB_WITH_ZONE_FILL, result.text) == []


def test_rejects_uuidless_footprint_collision_edit() -> None:
    with pytest.raises(RoutingError, match="routing changed placement"):
        route_pcb(PCB_UUIDLESS_FOOTPRINTS, engine=_EditFirstUuidlessFootprintEngine())


def test_rejects_deleted_uuidless_zone_among_identical() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_UUIDLESS_ZONES, engine=_DeleteFirstUuidlessZoneEngine())


def test_rejects_replaced_uuidless_zone_among_identical() -> None:
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: zone"):
        route_pcb(PCB_UUIDLESS_ZONES, engine=_ReplaceFirstUuidlessZoneEngine())


GRAPHIC_A = '''  (gr_line
    (start 0 0)
    (end 10 0)
    (stroke (width 0.1) (type default))
    (layer "Edge.Cuts")
    (uuid "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1")
  )
'''
GRAPHIC_B = GRAPHIC_A.replace("(end 10 0)", "(end 0 10)").replace("bbb1", "bbb2")


class _TextEngine:
    """Routes by returning the board text through one function."""

    def __init__(self, transform) -> None:
        self._transform = transform

    def route(self, pcb_text: str, *, timeout_s: float, max_passes: int, keep_existing_tracks: bool) -> str:
        del timeout_s, max_passes, keep_existing_tracks
        return self._transform(pcb_text)


def test_allows_the_same_graphics_written_in_another_order() -> None:
    # KiCad 9.0.9 writes a board's graphic items in a different order than 9.0.2 and the items are unchanged.
    board = _insert_before_close(MINIMAL_PCB, GRAPHIC_A + GRAPHIC_B)
    engine = _TextEngine(lambda text: text.replace(GRAPHIC_A + GRAPHIC_B, GRAPHIC_B + GRAPHIC_A))
    result = route_pcb(board, engine=engine)
    assert result.text.index(GRAPHIC_B) < result.text.index(GRAPHIC_A)


def test_rejects_an_edited_graphic_even_when_the_order_also_changed() -> None:
    board = _insert_before_close(MINIMAL_PCB, GRAPHIC_A + GRAPHIC_B)
    moved = GRAPHIC_A.replace("(end 10 0)", "(end 11 0)")
    engine = _TextEngine(lambda text: text.replace(GRAPHIC_A + GRAPHIC_B, GRAPHIC_B + moved))
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks: gr_line"):
        route_pcb(board, engine=engine)


def test_rejects_one_graphic_standing_in_for_its_duplicate() -> None:
    # Same count, same set of distinct items, different multiplicity: A, A, B becomes A, B, B.
    board = _insert_before_close(MINIMAL_PCB, GRAPHIC_A + GRAPHIC_A + GRAPHIC_B)
    engine = _TextEngine(lambda text: text.replace(GRAPHIC_A + GRAPHIC_A + GRAPHIC_B, GRAPHIC_A + GRAPHIC_B + GRAPHIC_B))
    with pytest.raises(RoutingError, match=r"routing changed more than copper tracks"):
        route_pcb(board, engine=engine)
