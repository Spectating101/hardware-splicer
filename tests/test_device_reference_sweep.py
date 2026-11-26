"""Device reference sweep: file classification and completeness, without the network."""
from datetime import datetime, timezone

from hardware_splicer import device_reference_sweep as drs


def test_files_are_classified_into_design_parts():
    paths = ["cad/chassis.step", "pcb/main.kicad_pcb", "firmware/src/main.cpp", "docs/BOM.csv", "docs/assembly_guide.md",
             "urdf/robot.urdf", "README.md"]
    counts = drs.classify_files(paths)
    assert all(counts[k] == 1 for k in ("cad", "pcb", "firmware", "bom", "assembly", "sim"))
    assert drs.completeness(counts) == 5
    assert drs.completeness(drs.classify_files(["src/app.py", "README.md"])) == 0


def test_build_probes_the_top_of_each_category_with_an_injected_fetch():
    repo = {"full_name": "a/vac", "html_url": "u", "stargazers_count": 500, "pushed_at": "2026-11-01T00:00:00Z",
            "license": {"spdx_id": "MIT"}, "default_branch": "main", "description": "vacuum"}
    found = {"a/vac": {"repo": repo, "categories": {"robot_vacuum"}, "queries": {"q"}}}
    tree = {"sha": "x", "tree": [{"type": "blob", "path": p}
                                 for p in ("a.step", "b.kicad_pcb", "platformio.ini", "bom.csv", "assembly.md")]}
    report = drs.build(found, probe_top=3, now=datetime(2026, 11, 27, tzinfo=timezone.utc), fetch=lambda args: tree)
    assert report["summary"]["robot_vacuum"]["open_designs"] == 1
    assert report["repos"][0]["design"]["completeness"] == 5


def test_an_unlicensed_repository_never_counts_as_an_open_design():
    repo = {"full_name": "b/vac", "html_url": "u", "stargazers_count": 900, "pushed_at": "2026-11-01T00:00:00Z",
            "license": None, "default_branch": "main", "description": ""}
    found = {"b/vac": {"repo": repo, "categories": {"robot_vacuum"}, "queries": {"q"}}}
    tree = {"tree": [{"type": "blob", "path": p} for p in ("a.step", "b.kicad_pcb", "platformio.ini", "bom.csv", "assembly.md")]}
    report = drs.build(found, probe_top=3, now=datetime(2026, 11, 27, tzinfo=timezone.utc), fetch=lambda args: tree)
    assert report["summary"]["robot_vacuum"]["open_designs"] == 0


def test_submodules_are_listed_so_a_split_design_is_not_read_as_empty():
    tree = {"tree": [{"type": "commit", "path": "hardware"}, {"type": "commit", "path": "firmware"},
                     {"type": "blob", "path": "README.md"}]}
    design = drs.probe("x/mower", "main", fetch=lambda args: tree)
    assert design["completeness"] == 0 and design["submodules"] == ["hardware", "firmware"]
