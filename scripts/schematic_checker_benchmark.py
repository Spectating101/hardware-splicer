"""Run three schematic checkers on the before/after of real fix commits and record which findings the fix made disappear.

    python3 scripts/schematic_checker_benchmark.py cases.json out_dir <HS src dir>

For each case: fetch the schematic files of the project at the fix's parent (buggy) and at the fix (fixed), then run
  1. KiCad's own ERC (kicad-cli sch erc),
  2. kicad-happy's deterministic schematic analyser (network-isolated with bwrap),
  3. HS: KiCad netlist export -> hardware_splicer.netlist.import_kicad + netlist.erc.
A finding "resolved by the fix" is one present before and absent after. Whether it is the bug is judged by hand later.

Every checker runs on the project's root sheet (the .kicad_sch named after its .kicad_pro), not on the sheet the fix
touched: a sub-sheet exported alone loses every connection that crosses the hierarchy. A file saved by a newer KiCad
than the system kicad-cli is retried with HARDWARE_SPLICER_KICAD_CLI (for example a KiCad 10 wrapper).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
# kicad-happy (MIT, github.com/aklofas/kicad-happy) is not bundled: point HS_KICAD_HAPPY at its analyze_schematic.py.
KH = Path(os.environ.get("HS_KICAD_HAPPY", HERE / "tools/kicad-happy/skills/kicad/scripts/analyze_schematic.py"))
HS_SRC = Path(sys.argv[3]) if len(sys.argv) > 3 else None
NEWER_CLI = os.environ.get("HARDWARE_SPLICER_KICAD_CLI")


def cli(args, timeout=300):
    """kicad-cli, retried with HARDWARE_SPLICER_KICAD_CLI when the system one writes nothing (a newer file format)."""
    out = Path(args[args.index("--output") + 1])
    subprocess.run(["kicad-cli", *args], capture_output=True, text=True, timeout=timeout)
    if not out.exists() and NEWER_CLI:
        subprocess.run([NEWER_CLI, *args], capture_output=True, text=True, timeout=timeout * 3, cwd=str(Path(args[-1]).parent))
    return out.exists()


def project_root(src: Path, given: str) -> Path:
    """The project's root sheet, preferring the project whose hierarchy names the sheet the fix touched."""
    roots = [p.with_suffix(".kicad_sch") for p in sorted(src.glob("*.kicad_pro")) if p.with_suffix(".kicad_sch").exists()]
    for root in roots:
        if root.name == given or f'"{given}"' in root.read_text(encoding="utf-8", errors="replace"):
            return root
    return roots[0] if roots else src / given


def gh_json(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=90)
    return json.loads(r.stdout) if r.returncode == 0 else None


def fetch(repo, sha, schematic, dest):
    """Every .kicad_sch, .kicad_pro, sym-lib-table and .kicad_sym under the root schematic's folder, at sha."""
    tree = gh_json(f"repos/{repo}/git/trees/{sha}?recursive=1") or {}
    folder = str(Path(schematic).parent)
    folder = "" if folder == "." else folder + "/"
    keep = [t["path"] for t in tree.get("tree", []) if t["type"] == "blob" and t["path"].startswith(folder)
            and (t["path"].endswith((".kicad_sch", ".kicad_pro", ".kicad_sym")) or t["path"].endswith("sym-lib-table"))]
    for path in keep[:80]:
        out = dest / path[len(folder):]
        out.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["curl", "-sSL", "--max-time", "60", "-o", str(out), f"https://raw.githubusercontent.com/{repo}/{sha}/{quote(path)}"],
                           capture_output=True, timeout=90)
        if r.returncode != 0:
            out.unlink(missing_ok=True)
    return project_root(dest, Path(schematic).name)


def kicad_erc(root, work):
    out = work / "kicad_erc.json"
    if not cli(["sch", "erc", "--format", "json", "--severity-all", "--output", str(out), str(root)]):
        return None
    data = json.loads(out.read_text())
    rows = []
    for sheet in data.get("sheets", []):
        for v in sheet.get("violations", []):
            items = ";".join(sorted(re.sub(r"\s+", " ", i.get("description", "")) for i in v.get("items", [])))
            rows.append(f"{v.get('type')}|{items}")
    return rows


def kicad_happy(root, work):
    out = work / "kicad_happy.json"
    cmd = ["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--bind", str(work), str(work), "--bind", str(root.parent), str(root.parent),
           "--dev", "/dev", "--proc", "/proc", "python3", "-I", str(KH), str(root), "--only-deterministic", "--compact", "-o", str(out)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not out.exists():
        return None
    data = json.loads(out.read_text())
    rows = []
    for f in data.get("findings", []):
        refs = ",".join(sorted(map(str, f.get("components") or f.get("refs") or [])))[:120]
        rows.append(f"{f.get('rule_id') or f.get('detector')}|{f.get('severity')}|{refs}|{str(f.get('summary', ''))[:120]}")
    return rows


def hs_erc(root, work):
    net = work / "netlist.net"
    cli(["sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(net), str(root)])
    if not net.exists() or HS_SRC is None:
        return None
    code = ("import json,sys;sys.path.insert(0,sys.argv[1]);from hardware_splicer.netlist.import_kicad import parse_kicad_netlist;"
            "from hardware_splicer.netlist.erc import run_erc;r=run_erc(parse_kicad_netlist(open(sys.argv[2]).read()));"
            "print(json.dumps(r,default=str))")
    run = subprocess.run(["python3", "-c", code, str(HS_SRC), str(net)], capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        return {"error": run.stderr.strip().splitlines()[-1][:300] if run.stderr.strip() else "failed"}
    data = json.loads(run.stdout)
    return [f"{v.get('rule')}|{v.get('message', '')[:140]}" for v in data.get("violations", [])]


def hs_review(root, work):
    """HS's general KiCad review (hardware_splicer.kicad_design_review) on the same exported netlist."""
    net = work / "netlist.net"
    if not net.exists() or HS_SRC is None:
        return None
    code = ("import json,sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;"
            "from hardware_splicer.kicad_design_review import review_schematic;print(json.dumps(review_schematic(Path(sys.argv[2]))))")
    run = subprocess.run(["python3", "-c", code, str(HS_SRC), str(net)], capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        return {"error": run.stderr.strip().splitlines()[-1][:300] if run.stderr.strip() else "failed"}
    return [f"{f['rule']}|{f.get('net', '')}|{','.join(f['components'])}" for f in json.loads(run.stdout)["findings"]]


def main():
    cases = json.loads(Path(sys.argv[1]).read_text())
    out_dir = Path(sys.argv[2]).resolve()
    results = []
    for case in cases:
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{case['repo']}_{case['sha'][:8]}")
        row = {**case, "checkers": {}}
        try:
            roots = {}
            for side, sha in (("before", case["parent"]), ("after", case["sha"])):
                work = out_dir / name / side
                work.mkdir(parents=True, exist_ok=True)
                roots[side] = (fetch(case["repo"], sha, case["schematic"], work / "src").resolve(), work)
            row["root"] = roots["after"][0].name
            for checker, fn in (("kicad_erc", kicad_erc), ("kicad_happy", kicad_happy), ("hs", hs_erc), ("hs_review", hs_review)):
                before, after = (fn(*roots[s]) for s in ("before", "after"))
                if not isinstance(before, list) or not isinstance(after, list):
                    row["checkers"][checker] = {"ran": False, "detail": before if isinstance(before, dict) else after}
                    continue
                gone = sorted(set(before) - set(after))
                row["checkers"][checker] = {"ran": True, "before": len(before), "after": len(after), "resolved_by_fix": gone[:40]}
        except Exception as exc:  # one broken case must not stop the run
            row["error"] = f"{type(exc).__name__}: {exc}"[:300]
        results.append(row)
        (out_dir / "results.json").write_text(json.dumps(results, indent=1))
        print(case["repo"], case["sha"][:8], {k: (v.get("resolved_by_fix") and len(v["resolved_by_fix"])) if v.get("ran") else "not run"
                                              for k, v in row["checkers"].items()}, flush=True)


if __name__ == "__main__":
    main()
