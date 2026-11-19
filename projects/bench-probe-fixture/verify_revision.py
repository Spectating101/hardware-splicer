"""Reproduce the moved-pad experiment against the supplied STEP models."""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import cadquery as cq

from build import BOARD, HERE, PROBE_BORE, build, exported_centres


MOVE_PAD = """
import pcbnew
import sys

board = pcbnew.LoadBoard(sys.argv[1])
board.FindFootprintByReference("TP12").Move(pcbnew.VECTOR2I(pcbnew.FromMM(2), 0))
pcbnew.SaveBoard(sys.argv[2], board)
"""


def verify():
    with TemporaryDirectory() as directory:
        output = Path(directory)
        variant = output / "revised.kicad_pcb"
        subprocess.run(["/usr/bin/python3", "-c", MOVE_PAD, BOARD, variant], check=True)
        build(variant, output, "/usr/bin/python3")
        original = set(exported_centres(HERE / "probe-guide.step", PROBE_BORE, 4))
        revised = set(exported_centres(output / "probe-guide.step", PROBE_BORE, 4))
        if original - revised != {(60, 12)} or revised - original != {(62, 12)}:
            raise ValueError("Expected exactly the TP12 bore to move 2 mm")
        a = cq.importers.importStep(str(HERE / "board-carrier.step")).val()
        b = cq.importers.importStep(str(output / "board-carrier.step")).val()
        if max(a.cut(b).Volume(), b.cut(a).Volume()) > 1e-8:
            raise ValueError("Pad relocation unexpectedly changed the board carrier")
        print("Only the TP12 bore moved. The board carrier is geometrically identical.")


if __name__ == "__main__":
    verify()
