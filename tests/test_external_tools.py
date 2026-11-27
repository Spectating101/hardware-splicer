"""The limb registry: every tool has a licence and a status, copyleft tools are never copied in, and records exist."""
from pathlib import Path

from hardware_splicer import external_tools as et

ROOT = Path(__file__).resolve().parents[1]


def test_every_tool_names_its_licence_status_and_how_hs_uses_it():
    reg = et.registry()
    for t in reg["tools"]:
        assert t["licence"] and t["how"] and t["status"] in reg["statuses"], t["name"]
        if any(c in t["licence"] for c in et.COPYLEFT):
            assert any(w in t["how"] for w in ("separate", "candidate", "jar")), t["name"]  # run separately, never copied in
        if t["licence"] == "none":
            assert t["status"] == "reference" and "not copied" in t["how"], t["name"]


def test_every_cited_record_exists_in_the_repository():
    for t in et.registry()["tools"]:
        if t.get("record"):
            assert (ROOT / t["record"]).exists(), (t["name"], t["record"])


def test_the_summary_counts_by_role_and_status():
    s = et.summary()
    assert s["tools"] == len(et.registry()["tools"]) and s["by_role"]["routing"]["integrated"] >= 2


def test_the_toolbelt_lists_the_routers():
    from hardware_splicer import engineering_toolbelt as tb

    env = tb.call("hs_external_tools", {"role": "routing"})
    assert env["ok"] and {t["name"] for t in env["result"]["tools"]} >= {"FreeRouting", "Copper (copper-kicad-mcp)"}
