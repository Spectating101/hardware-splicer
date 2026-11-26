"""HS's engineering tools for any agent, over MCP or REST, each working on one objective project.

Every tool returns the same envelope:

    {"tool", "ok", "summary", "problems": [...], "result": {...}, "sources": [...], "claim_boundary", "project_step"}

``problems`` lists what the tool itself found wrong or refused (a failed check, an unsupported input, a missing source);
``ok`` is false whenever it is not empty. ``claim_boundary`` says what only a physical build can show. When a call names
a ``project_id``, the step is recorded on that project (see ``objective_project``), so an agent's research, decisions and
checks stay on one project and ``hs_project_status`` can separate software-checked, open and physical-only items.

Tools that need CAD or simulation libraries run in the native interpreter named by HARDWARE_SPLICER_DIGITAL_PYTHON.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .objective_project import ObjectiveProject
from .state_paths import repo_root

REPO = repo_root()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any], ObjectiveProject | None], dict[str, Any]]
    check_key: Callable[[dict[str, Any]], str] | None = None
    category: str = "check"  # check: verifies something; research: finds information; artifact: writes a deliverable


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    props = {"project_id": {"type": "string", "description": "Objective project to record this step on (optional)."}, **props}
    return {"type": "object", "properties": props, "required": required or []}


def _envelope(ok: bool, summary: str, result: Any, *, problems: list[str] | None = None, sources: list[str] | None = None,
              boundary: str | None = None) -> dict[str, Any]:
    problems = list(problems or [])
    return {"ok": ok and not problems, "summary": summary, "problems": problems, "result": result,
            "sources": sorted(set(sources or [])), "claim_boundary": boundary}


def _findings_problems(result: dict[str, Any]) -> list[str]:
    return [f"{f.get('rule')}: {f.get('message')}" for f in result.get("findings", []) if f.get("severity") == "error"]


def _project_path(project: ObjectiveProject | None, sub: str) -> Path:
    if project is None:
        raise ValueError("this tool writes files: give a project_id (open one with hs_project_open)")
    path = project.artifacts_dir / sub
    path.mkdir(parents=True, exist_ok=True)
    return path


def _readable(path: str, project: ObjectiveProject | None) -> Path:
    """Inputs may come from the project's own artifacts or from this repository, nowhere else."""
    p = Path(path)
    if not p.is_absolute():
        p = (project.root / p) if project else (REPO / p)
    p = p.resolve()
    allowed = [REPO.resolve()] + ([project.root.resolve()] if project else [])
    if not any(p == a or a in p.parents for a in allowed):
        raise ValueError(f"path outside the project and the repository: {path}")
    if not p.is_file():
        raise FileNotFoundError(path)
    return p


def _native_python() -> str:
    py = os.environ.get("HARDWARE_SPLICER_DIGITAL_PYTHON")
    if not py or not Path(py).is_file():
        raise RuntimeError("set HARDWARE_SPLICER_DIGITAL_PYTHON to the interpreter with cadquery/pybullet/gmsh")
    return py


# ---------------------------------------------------------------------------------------------------- project


def _project_open(args, _project):
    p = ObjectiveProject.open(str(args.get("objective") or ""), constraints=args.get("constraints"), acceptance=args.get("acceptance"))
    return _envelope(True, f"opened {p.project_id}", {"project_id": p.project_id, "objective": p.objective()})


def _project_record(args, project):
    if project is None:
        raise ValueError("project_id is required")
    kind = str(args.get("kind") or "note")
    if kind not in ("research", "decision", "note"):
        raise ValueError("kind must be research, decision or note (tool steps are recorded by the tools themselves)")
    if kind == "decision" and not (args.get("choice") and args.get("because")):
        raise ValueError("a decision needs a choice and the reason for it")
    payload = {k: args[k] for k in ("sources", "choice", "because", "alternatives", "details") if k in args}
    step = project.record(kind, str(args.get("title") or kind), payload)
    return _envelope(True, f"recorded step {step['seq']}", step)


def _write_artifact(args, project):
    """A text deliverable the agent wrote (firmware, config, wiring list, procedure), kept on the project."""
    if project is None:
        raise ValueError("project_id is required")
    rel = Path(str(args.get("path") or ""))
    if not str(rel) or rel.is_absolute() or ".." in rel.parts:
        raise ValueError("path must be relative inside the project's artifacts")
    content = str(args.get("content") or "")
    if len(content.encode()) > 512_000:
        raise ValueError("artifact over 512 kB; write it in parts")
    target = project.artifacts_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return _envelope(True, f"wrote artifacts/{rel} ({len(content)} chars)", {"path": f"artifacts/{rel}", "purpose": args.get("purpose")},
                     sources=list(args.get("sources") or []),
                     boundary=args.get("claim_boundary") or "Written, not run on hardware.")


def _project_status(args, project):
    if project is None:
        raise ValueError("project_id is required")
    st = project.status()
    return _envelope(True, f"{st['steps']} steps; {len(st['software_checked'])} checked, {len(st['open'])} open", st)


# ---------------------------------------------------------------------------------------------------- prior art


UA = {"User-Agent": "hardware-splicer-prior-art"}


def _get(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as resp:  # noqa: S310 - fixed hosts
        return resp.read().decode("utf-8", "replace")


def _boardrepo(query: str, limit: int) -> list[dict[str, Any]]:
    page = _get("https://boardrepo.com/browse?q=" + urllib.parse.quote(query))
    skip = {"brand", "docs", "about", "guides", "_next", "api", "connect", "browse", "contact", "dashboard", "changelog"}
    slugs = []
    for m in re.finditer(r'href="/([a-z0-9_.-]+)/([a-z0-9_.-]+)"', page):
        if m.group(1) not in skip and f"{m.group(1)}/{m.group(2)}" not in slugs:
            slugs.append(f"{m.group(1)}/{m.group(2)}")
    out = []
    for slug in slugs[:limit]:
        entry: dict[str, Any] = {"board": slug, "url": f"https://boardrepo.com/{slug}"}
        try:
            md = _get(f"https://boardrepo.com/{slug}.md")
            for key in ("title", "description"):
                m = re.search(rf'^{key}: "(.*)"$', md, re.M)
                if m:
                    entry[key] = html.unescape(m.group(1))[:160]
            for key, rx in (("copper_layers", r"\| Copper layers \| (\d+)"), ("size", r"\| Size \| ([^|]+)\|"),
                            ("contents", r"## Contents\n\n((?:- .*\n)+)")):
                m = re.search(rx, md)
                if m:
                    entry[key] = m.group(1).strip().replace("\n- ", ", ").lstrip("- ")
        except Exception as exc:  # noqa: BLE001 - one unreadable board must not sink the search
            entry["error"] = type(exc).__name__
        out.append(entry)
    return out


def _github_code(query: str, extension: str, limit: int) -> list[dict[str, Any]]:
    gh = shutil.which("gh")
    if not gh:
        return [{"error": "gh CLI not available"}]
    run = subprocess.run([gh, "search", "code", query, "--extension", extension, "--limit", str(limit), "--json", "repository,path"],
                         capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        return [{"error": run.stderr.strip()[:200]}]
    hits, licences = json.loads(run.stdout or "[]"), {}
    out = []
    for h in hits:
        repo = h["repository"]["nameWithOwner"]
        if repo not in licences:
            info = subprocess.run([gh, "api", f"repos/{repo}", "--jq", ".license.spdx_id // \"NONE\""], capture_output=True, text=True, timeout=30)
            licences[repo] = info.stdout.strip() or "unknown"
        out.append({"repo": repo, "path": h["path"], "licence": licences[repo], "url": f"https://github.com/{repo}/blob/HEAD/{h['path']}"})
    return out


def _github_repos(query: str, limit: int) -> list[dict[str, Any]]:
    """Whole projects (apps, firmware, robot platforms), most-starred first: prior art that has no KiCad file. GitHub's
    repository search matches description words exactly ("smartphone" misses "smartphones"), so the query's words are
    also tried as topics, which is how OpenBot (topics smartphone, robot) is found."""
    gh = shutil.which("gh")
    if not gh:
        return [{"error": "gh CLI not available"}]
    fields = "fullName,description,stargazersCount,license,pushedAt,url"
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", query)][:3]
    runs = [[gh, "search", "repos", query, "--sort", "stars", "--limit", str(limit), "--json", fields]]
    if words:
        runs.append([gh, "search", "repos", "--sort", "stars", "--limit", str(limit), "--json", fields]
                    + [a for w in words for a in ("--topic", w)])
    found: dict[str, dict[str, Any]] = {}
    errors = []
    for cmd in runs:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if run.returncode != 0:
            errors.append(run.stderr.strip()[:200]); continue
        for r in json.loads(run.stdout or "[]"):
            found.setdefault(r["fullName"], {"repo": r["fullName"], "stars": r.get("stargazersCount"),
                                             "licence": (r.get("license") or {}).get("key") or "none", "pushed": (r.get("pushedAt") or "")[:10],
                                             "description": (r.get("description") or "")[:200], "url": r["url"]})
    out = sorted(found.values(), key=lambda r: -(r["stars"] or 0))[:limit]
    if not out and errors:
        return [{"error": "; ".join(errors)}]
    return out


OWN_DIRS = ("docs", "examples", "projects")
URL_RX = re.compile(r"https?://[^\s\"'<>)\]]+")


def _hs_own(query: str, limit: int) -> list[dict[str, Any]]:
    """What HS has already found: its own docs, examples and project records, and the weekly landscape register.
    Prior findings are worthless if the next project cannot see them (OpenBot was recorded on 2026-11-26 and then
    missed the same day)."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9+_-]{2,}", query)]
    if not words:
        return []
    root = REPO
    files = [f for d in OWN_DIRS for f in (root / d).rglob("*") if f.suffix in (".md", ".json", ".jsonl") and f.is_file()
             and f.stat().st_size < 2_000_000]
    register = Path(os.path.expanduser("~/.local/share/hs-landscape/register.json"))
    if register.is_file():
        files.append(register)
    hits = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        low = text.lower()
        matched = [w for w in words if w in low]
        if not matched:
            continue
        urls = []
        for m in URL_RX.finditer(text):
            window = low[max(0, m.start() - 300): m.end() + 300]
            if any(w in window for w in matched) and m.group(0) not in urls:
                urls.append(m.group(0))
        name = str(f.relative_to(root)) if root in f.parents else str(f)
        hits.append({"file": name, "matched": matched, "score": len(matched) / len(words), "urls": urls[:12]})
    # HS's own source: every module's name and description, so a capability HS already has is found before it is
    # rebuilt (on 2026-11-26 FEM, thermal review and arm kinematics were called "missing" while 600 modules sat unread)
    pkg = Path(__file__).resolve().parent
    for f in pkg.rglob("*.py"):
        if "__pycache__" in f.parts or f.name == "__init__.py":
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:3000]
        except OSError:
            continue
        m = re.search(r'^\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', head, re.S)
        doc = (m.group(1) if m else "").strip()
        text = (f.stem.replace("_", " ") + " " + doc).lower()
        matched = [w for w in words if w in text]
        if matched:
            hits.append({"file": str(f.relative_to(root)) if root in f.parents else str(f), "matched": matched,
                         "score": len(matched) / len(words), "urls": [], "module": f.stem, "about": " ".join(doc.split())[:240]})
    hits.sort(key=lambda h: (-h["score"], -len(h["urls"]), "module" in h))
    return hits[:limit]


def _junk_lookup(args, _project):
    from . import junk_catalogue
    needs = [str(n) for n in (args.get("needs") or [])]
    if not needs:
        raise ValueError("needs is required: capabilities such as drive_motors, camera, wifi_compute, battery_cells")
    res = junk_catalogue.lookup(needs)
    plan = ", ".join(f"{d['device']} ({'/'.join(d['covers'])})" for d in res["donor_plan"]) or "none"
    problems = [f"no junk in the catalogue gives {n}: buy or build it" for n in res["not_covered_by_junk"]]
    sources = sorted({u for d in res["donor_plan"] for u in d.get("reuse", [])})
    return _envelope(True, f"donors: {plan}", res, problems=problems, sources=sources,
                     boundary="Typical contents of discarded devices; a donor's parts are unknown until it is opened and tested.")


def _prior_art(args, _project):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    limit = int(args.get("limit") or 8)
    sources = args.get("sources") or ["hs_own", "github_repos", "boardrepo", "github"]
    result: dict[str, Any] = {"query": query}
    if "hs_own" in sources:
        result["hs_own"] = _hs_own(query, limit)
    if "github_repos" in sources:
        result["github_repos"] = _github_repos(query, limit)
    if "boardrepo" in sources:
        result["boardrepo"] = _boardrepo(query, limit)
    if "github" in sources:
        result["github_kicad"] = _github_code(query, str(args.get("extension") or "kicad_sch"), limit)
    ok_lic = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC-BY-4.0", "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "cc-by-4.0")
    reusable = [g for g in result.get("github_kicad", []) + result.get("github_repos", []) if g.get("licence") in ok_lic]
    result["reuse_note"] = ("MIT, Apache, BSD and CC BY work can be adopted with attribution; GPL/AGPL/CERN-OHL-S and "
                            "unlicensed ones are reference only or run as separate programs. A published design is not evidence "
                            "that it was built or works. Consumer marketplaces (Shopee, AliExpress, Amazon) are not searched "
                            "here: check them for a finished product too.")
    seen = [u for h in result.get("hs_own", []) for u in h["urls"]]
    return _envelope(True, f"{len(result.get('hs_own', []))} of HS's own records, {len(result.get('github_repos', []))} GitHub projects, "
                     f"{len(result.get('boardrepo', []))} BoardRepo boards, {len(result.get('github_kicad', []))} GitHub KiCad files "
                     f"({len(reusable)} with a reusable licence)", result,
                     sources=["https://boardrepo.com/browse?q=" + urllib.parse.quote(query)] + [g["url"] for g in result.get("github_repos", []) if g.get("url")] + seen[:10])


def _read_board(args, _project):
    slug = str(args.get("board") or "")
    if not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", slug):
        raise ValueError("board must be handle/slug as listed by hs_prior_art_search")
    md = _get(f"https://boardrepo.com/{slug}.md")
    return _envelope(True, f"read {slug}", {"board": slug, "markdown": md[: int(args.get("max_chars") or 6000)]},
                     sources=[f"https://boardrepo.com/{slug}"])


# ---------------------------------------------------------------------------------------------------- sizing and checks


def _arm(args, _project):
    from . import arm_actuator_sizing as aas
    links = [float(x) for x in args["links_mm"]]
    rows = aas.cited_servo_rows(float(args["supply_v"]))
    res = aas.pick(links, float(args["payload_kg"]), float(args.get("safety_factor", 1.5)), rows,
                   float(args["max_stall_share"]), args.get("link_g_per_m"))
    problems = [f"joint {j['joint']}: {j['status']}" for j in res["joints"] if j["status"] != "picked"]
    return _envelope(res["feasible"], "feasible" if res["feasible"] else "no cited actuator holds every joint", res,
                     problems=problems, sources=[r["source"] for r in rows], boundary=res["claim_boundary"])


def _drive(args, _project):
    from . import drive_sizing
    res = drive_sizing.size(float(args["mass_kg"]), float(args["wheel_mm"]), int(args.get("driven", 2)), float(args["speed_m_s"]),
                            float(args.get("slope_deg", 0)), **{k: float(args[k]) for k in ("crr", "accel_m_s2") if k in args})
    best = res["passing"][0] if res["passing"] else None
    summary = (f"{len(res['passing'])} of {res['options_checked']} gearmotor options pass; best {best['family']} {best['ratio']}:1"
               if best else "no cited gearmotor passes")
    return _envelope(bool(best), summary, res, problems=[] if best else ["no cited gearmotor meets speed, torque and current limits"],
                     sources=res["sources"], boundary=res["claim_boundary"])


def _propulsion(args, _project):
    from . import propulsion_check
    res = propulsion_check.check_propulsion(args["spec"], args.get("table"))
    return _envelope(True, f"{res['summary']['errors']} errors, {res['summary']['warnings']} warnings", res,
                     problems=_findings_problems(res), sources=[str(res.get("table", {}).get("source") or "")], boundary=res["claim_boundary"])


def _energy(args, _project):
    from . import energy_budget
    res = energy_budget.check_energy(args["spec"])
    return _envelope(True, f"{res['summary']['errors']} errors, {res['summary']['warnings']} warnings", res,
                     problems=_findings_problems(res), boundary=res["claim_boundary"])


def _price(args, _project):
    from . import jlcparts_lookup
    if args.get("lines"):
        res = jlcparts_lookup.price_bom(list(args["lines"]), boards=int(args.get("boards", 1)))
        problems = [f"not found: {m.get('query') or m.get('lcsc')}" for m in res["not_found"]]
        notes = [f"{','.join(l.get('refs', []))}: keyword match {l['lcsc']} {l['mpn']}, check: {l['description']}"
                 for l in res["lines"] if l["match"].startswith("keyword")]
        res["check_these"] = notes
        return _envelope(True, f"US${res['per_board_usd']} per board ({res['boards']} boards), {len(res['not_found'])} not found", res,
                         problems=problems, sources=[jlcparts_lookup.SOURCE], boundary=res["claim_boundary"])
    hits = jlcparts_lookup.search(str(args["query"]), limit=int(args.get("limit", 5)), qty=int(args.get("qty", 1)))
    return _envelope(bool(hits), f"{len(hits)} parts", hits, problems=[] if hits else ["no JLCPCB part matches"],
                     sources=[jlcparts_lookup.SOURCE])


def _review_schematic(args, project):
    from . import kicad_design_review
    res = kicad_design_review.review_schematic(_readable(str(args["schematic"]), project), args.get("mates"))
    findings = res.get("findings", [])
    problems = [f"{f.get('rule')}: {f.get('message') or f.get('detail')}" for f in findings if f.get("severity", "error") == "error"]
    return _envelope(True, f"{len(findings)} findings", res, problems=problems)


def _component_board(args, project):
    from . import component_board_pipeline as cbp
    spec = args["design"]
    stages = tuple(args.get("stages") or ["schematic"])
    out = _project_path(project, f"boards/{spec['name']}")
    res = cbp.run(spec, out, stages=stages)
    if project:
        res["files_in_project"] = sorted(str(p.relative_to(project.root)) for p in out.rglob("*") if p.is_file())
    return _envelope(res["ok"], f"{spec['name']}: " + ", ".join(f"{k} {'ok' if v['ok'] else 'FAILED'}" for k, v in res["stages"].items()),
                     res, problems=res["problems"],
                     boundary="Schematic, layout and files checked in software only; nothing fabricated, assembled or powered.")


def _native_tool(module: str, argv: list[str], timeout: int = 900) -> dict[str, Any]:
    run = subprocess.run([_native_python(), "-m", f"hardware_splicer.{module}", *argv], capture_output=True, text=True,
                         timeout=timeout, env={**os.environ, "PYTHONPATH": str(REPO / "src")}, cwd=str(REPO))
    if run.returncode != 0:
        raise RuntimeError(f"{module} failed: {run.stderr[-1200:]}")
    return json.loads(run.stdout)


def _motion(args, project):
    urdf = _readable(str(args["urdf"]), project)
    res = _native_tool("motion_sweep", ["--urdf", str(urdf), "--steps", str(int(args.get("steps", 31)))])
    sweeps = res.get("sweeps") or []
    clashes = [(",".join(s["joints"]), s["clash_steps"], s.get("clashing_pairs")) for s in sweeps if s.get("clash_steps")]
    return _envelope(True, f"{len(sweeps)} sweeps, {len(clashes)} with clashes", res,
                     problems=[f"{j}: {n} clash steps {pairs}" for j, n, pairs in clashes], boundary=res.get("claim_boundary"))


def _rover_chassis(args, project):
    out = _project_path(project, "cad/rover_chassis")
    params = out / "params.json"
    params.write_text(json.dumps(args.get("params") or {}))
    res = _native_tool("rover_chassis", ["--params", str(params), "--out", str(out)])
    if project:
        res["files_in_project"] = sorted(str(p.relative_to(project.root)) for p in out.rglob("*") if p.is_file())
    return _envelope(True, res.get("summary", "chassis built"), res, problems=res.get("problems", []),
                     sources=res.get("sources", []), boundary=res.get("claim_boundary"))


def _bom_check(args, _project):
    """A parts list against a budget: every line must name where its price came from, and the list must show what was
    salvaged. HS exists to turn junk into working hardware, so a list with no reused part needs a recorded reason."""
    lines = list(args.get("lines") or [])
    if not lines:
        raise ValueError("lines are required: [{item, qty, unit_usd, source, origin?}]")
    budget = args.get("budget_usd")
    problems, rows, total = [], [], 0.0
    new_spend, salvaged, diverted_g, replaced_usd = 0.0, [], 0.0, 0.0
    for i, line in enumerate(lines):
        qty, unit = float(line.get("qty", 1)), line.get("unit_usd")
        origin = str(line.get("origin") or "new").lower()
        if origin not in ("new", "used", "salvaged"):
            problems.append(f"{line.get('item', i)}: origin must be new, used or salvaged")
            origin = "new"
        if unit is None:
            problems.append(f"{line.get('item', i)}: no price (a salvaged part is priced at what it costs to get, often 0)")
            continue
        ext = qty * float(unit)
        total += ext
        source = str(line.get("source") or "")
        if origin == "salvaged":
            # a salvaged part is cited by the donor it comes out of, not a shop page
            if not source.startswith(("donor:", "http://", "https://")):
                problems.append(f"{line.get('item', i)}: a salvaged part must name its donor (source 'donor:<what it comes out of>')")
            salvaged.append(line.get("item", i))
            diverted_g += qty * float(line.get("mass_g") or 0)
            replaced_usd += qty * float(line.get("new_equivalent_usd") or 0)
        else:
            new_spend += ext
            if not source.startswith(("http://", "https://")):
                problems.append(f"{line.get('item', i)}: price has no source URL (declared, not cited)")
        rows.append({**line, "origin": origin, "extended_usd": round(ext, 2)})
    if budget is not None and total > float(budget):
        problems.append(f"total US${total:.2f} is over the US${float(budget):.2f} budget")
    reason = str(args.get("salvage_rejected_because") or "").strip()
    if not salvaged and not reason:
        problems.append("no salvaged part: HS's first strategy is reuse, so name the donors, or say why salvage does not fit "
                        "(salvage_rejected_because)")
    share = len(salvaged) / len(rows) if rows else 0.0
    salvage = {"salvaged_lines": len(salvaged), "salvage_share_of_lines": round(share, 2), "new_spend_usd": round(new_spend, 2),
               "mass_diverted_g": round(diverted_g, 1), "new_equivalent_replaced_usd": round(replaced_usd, 2),
               "salvage_rejected_because": reason or None}
    summary = (f"US${total:.2f} for {len(rows)} lines" + (f" against US${float(budget):.2f}" if budget is not None else "")
               + f"; {len(salvaged)} salvaged, US${new_spend:.2f} new")
    return _envelope(True, summary, {"lines": rows, "total_usd": round(total, 2), "budget_usd": budget, "salvage": salvage},
                     problems=problems,
                     sources=[str(l.get("source")) for l in lines if str(l.get("source") or "").startswith("http")],
                     boundary="Shop prices on the day they were read; shipping, tax and stock change. A salvaged part is "
                              "assumed to work until the donor is opened and the part is tested.")


# ---------------------------------------------------------------------------------------------------- registry


TOOLS: dict[str, ToolSpec] = {t.name: t for t in [
    ToolSpec("hs_project_open", "Open an objective project: the one place an engineering objective's research, decisions, "
             "checks and artifacts are kept. Returns project_id.",
             {"type": "object", "properties": {"objective": {"type": "string"}, "constraints": {"type": "object"},
                                               "acceptance": {"type": "array", "items": {"type": "string"}}}, "required": ["objective"]},
             _project_open),
    ToolSpec("hs_project_record", "Record research (with sources), a decision (choice, because, alternatives) or a note on a project.",
             _obj({"kind": {"type": "string", "enum": ["research", "decision", "note"]}, "title": {"type": "string"},
                   "sources": {"type": "array", "items": {"type": "string"}}, "choice": {"type": "string"},
                   "because": {"type": "string"}, "alternatives": {"type": "array"}, "details": {"type": "object"}},
                  ["project_id", "kind", "title"]), _project_record),
    ToolSpec("hs_project_write_artifact", "Save a text deliverable (software, config, wiring list, procedure) on the project, "
             "with its purpose, sources and what it has not been tested on.",
             _obj({"path": {"type": "string"}, "content": {"type": "string"}, "purpose": {"type": "string"},
                   "sources": {"type": "array", "items": {"type": "string"}}, "claim_boundary": {"type": "string"}},
                  ["project_id", "path", "content"]), _write_artifact, check_key=lambda a: f"artifact:{a.get('path')}",
             category="artifact"),
    ToolSpec("hs_project_status", "Where a project stands: software-checked items, open problems, what only a physical build "
             "can show, decisions, research and artifacts.", _obj({}, ["project_id"]), _project_status),
    ToolSpec("hs_junk_lookup", "Salvage first: which discarded devices (phones, robot vacuums, toy cars, laptop batteries, "
             "hoverboards, printers...) give the modules a design needs, the fewest donors that cover them, what to test first, "
             "hazards and prices last seen in Taiwan.",
             _obj({"needs": {"type": "array", "items": {"type": "string"}}}, ["needs"]), _junk_lookup, category="research"),
    ToolSpec("hs_prior_art_search", "Search what already exists before building: HS's own past findings (docs, examples, "
             "project records, the weekly landscape register), GitHub projects by stars, BoardRepo boards and GitHub KiCad files, "
             "with licences.",
             _obj({"query": {"type": "string"}, "limit": {"type": "integer"}, "sources": {"type": "array", "items": {"type": "string"}},
                   "extension": {"type": "string"}}, ["query"]), _prior_art, category="research"),
    ToolSpec("hs_read_board", "Read a public BoardRepo board (README, size, layers, contents) as markdown.",
             _obj({"board": {"type": "string"}, "max_chars": {"type": "integer"}}, ["board"]), _read_board, category="research"),
    ToolSpec("hs_size_arm_actuators", "Pick the lightest cited servo per arm joint for a payload, counting the servos' own weight, "
             "against a stated share of stall torque.",
             _obj({"links_mm": {"type": "array", "items": {"type": "number"}}, "payload_kg": {"type": "number"},
                   "safety_factor": {"type": "number"}, "supply_v": {"type": "number"}, "max_stall_share": {"type": "number"},
                   "link_g_per_m": {"type": "number"}}, ["links_mm", "payload_kg", "supply_v", "max_stall_share"]), _arm),
    ToolSpec("hs_size_rover_drive", "Which cited Pololu gearmotors drive a wheeled rover: speed, torque and current against the maker's limits.",
             _obj({"mass_kg": {"type": "number"}, "wheel_mm": {"type": "number"}, "driven": {"type": "integer"},
                   "speed_m_s": {"type": "number"}, "slope_deg": {"type": "number"}, "crr": {"type": "number"},
                   "accel_m_s2": {"type": "number"}}, ["mass_kg", "wheel_mm", "speed_m_s"]), _drive),
    ToolSpec("hs_check_propulsion", "Multirotor hover power, time, thrust-to-weight and margins from a cited motor bench table.",
             _obj({"spec": {"type": "object"}, "table": {"type": "object"}}, ["spec"]), _propulsion),
    ToolSpec("hs_energy_budget", "Battery energy budget: loads, runtime, surge, DC current and fuse window.",
             _obj({"spec": {"type": "object"}}, ["spec"]), _energy),
    ToolSpec("hs_price_parts", "JLCPCB/LCSC parts, stock and price breaks (jlcparts), for one query or a whole parts list.",
             _obj({"query": {"type": "string"}, "lines": {"type": "array"}, "boards": {"type": "integer"},
                   "qty": {"type": "integer"}, "limit": {"type": "integer"}}), _price),
    ToolSpec("hs_bom_check", "Total a parts list against a budget and report what was salvaged: every bought line needs a price "
             "and the URL it came from, every salvaged line (origin 'salvaged') the donor it comes out of; a list with no "
             "salvaged part needs salvage_rejected_because.",
             _obj({"lines": {"type": "array"}, "budget_usd": {"type": "number"}, "salvage_rejected_because": {"type": "string"}},
                  ["lines"]), _bom_check,
             check_key=lambda a: "bom_check"),
    ToolSpec("hs_review_kicad_schematic", "Review any KiCad schematic from KiCad's own netlist (UART crossings, power pins, I2C "
             "pull-ups, MOSFET orientation, USB-C CC).", _obj({"schematic": {"type": "string"}, "mates": {"type": "object"}}, ["schematic"]),
             _review_schematic),
    ToolSpec("hs_component_board", "Build a board from a component-level JSON design: schematic from the KiCad libraries with "
             "read-back parity and ERC; optionally the placed, FreeRouted PCB with DRC and schematic parity, and fab files.",
             _obj({"design": {"type": "object"}, "stages": {"type": "array", "items": {"type": "string", "enum": ["schematic", "pcb", "fab"]}}},
                  ["project_id", "design"]), _component_board, check_key=lambda a: f"board:{(a.get('design') or {}).get('name')}"),
    ToolSpec("hs_motion_sweep", "Sweep every joint of a URDF through its range and report collisions between links.",
             _obj({"urdf": {"type": "string"}, "steps": {"type": "integer"}}, ["urdf"]), _motion),
    ToolSpec("hs_rover_chassis", "Parametric printable rover chassis around cited gearmotor and camera dimensions, with tip-over, "
             "ground-clearance and print-bed checks.", _obj({"params": {"type": "object"}}, ["project_id"]), _rover_chassis,
             check_key=lambda a: "rover_chassis"),
]}


def tool_specs() -> list[ToolSpec]:
    return list(TOOLS.values())


def call(name: str, args: dict[str, Any] | None) -> dict[str, Any]:
    """Run one tool; errors and refusals come back in the envelope, never as a bare exception."""
    args = dict(args or {})
    spec = TOOLS.get(name)
    if spec is None:
        raise KeyError(f"unknown tool {name}")
    project = ObjectiveProject.load(args["project_id"]) if args.get("project_id") else None
    missing = [k for k in spec.schema.get("required", []) if k != "project_id" and args.get(k) in (None, "", [])]
    try:
        if missing:
            # say which inputs are missing and what they are, instead of a bare KeyError from inside the tool
            props = spec.schema.get("properties", {})
            raise ValueError("missing required input " + ", ".join(
                f"{k}" + (f" ({props[k].get('description')})" if props.get(k, {}).get("description") else "") for k in missing))
        env = spec.handler(args, project)
    except Exception as exc:  # noqa: BLE001 - reported to the agent, and recorded as an open problem
        env = _envelope(False, f"{type(exc).__name__}: {exc}", None, problems=[f"{type(exc).__name__}: {exc}"])
    env = {"tool": name, **env}
    if project and name not in ("hs_project_open", "hs_project_record", "hs_project_status"):
        inputs = {k: v for k, v in args.items() if k != "project_id"}
        step = project.record("tool", name, {"check_key": spec.check_key(args) if spec.check_key else name, "category": spec.category,
                                             "ok": env["ok"],
                                             "summary": env["summary"], "problems": env["problems"], "sources": env["sources"],
                                             "claim_boundary": env["claim_boundary"],
                                             "inputs": json.loads(json.dumps(inputs, default=str))})
        env["project_step"] = step["seq"]
    return env


if __name__ == "__main__":  # quick CLI: python -m hardware_splicer.engineering_toolbelt TOOL '{"json": "args"}'
    print(json.dumps(call(sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}")), indent=1, default=str))
