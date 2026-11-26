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


def _project_link_design(args, project):
    if project is None:
        raise ValueError("project_id is required")
    summary = project.link_design(str(args.get("design_project_id") or ""))
    return _envelope(True, f"linked {summary['project_id']} rev {summary['revision']}: achieved {summary['achieved_state']}, "
                     f"{len(summary['release_blockers'])} release blockers", summary, boundary=summary["authority"])


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


def _generated_map(f: Path, root: Path) -> bool:
    """The generated capability map repeats every module description, so it would match every query; modules are searched below."""
    rel = f.relative_to(root).as_posix() if root in f.parents else ""
    return rel in ("docs/CAPABILITY_MAP.md", "docs/capability_map.json") or rel.startswith("docs/capability_map/")


def _hs_own(query: str, limit: int) -> list[dict[str, Any]]:
    """What HS has already found: its own docs, examples and project records, and the weekly landscape register.
    Prior findings are worthless if the next project cannot see them (OpenBot was recorded on 2026-11-26 and then
    missed the same day)."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9+_-]{2,}", query)]
    if not words:
        return []
    root = REPO
    files = [f for d in OWN_DIRS for f in (root / d).rglob("*") if f.suffix in (".md", ".json", ".jsonl") and f.is_file()
             and f.stat().st_size < 2_000_000 and not _generated_map(f, root)]
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


def _capability_search(args, _project):
    """HS's own modules, from the generated capability map: search by words, or show one module's wiring."""
    from . import capability_map as cmap
    m = cmap.build()
    if args.get("module"):
        rows = {r["module"]: r for r in m["rows"]}
        row = rows.get(str(args["module"]))
        if row is None:
            raise ValueError(f"no module {args['module']}; search with query first")
        keep = ("module", "area", "status", "direct", "tool", "lines", "tests", "test_files", "importers", "imports", "scripts", "about")
        return _envelope(True, f"{row['module']}: {row['status']}, {row['tests']} tests", {k: row[k] for k in keep})
    words = re.findall(r"[A-Za-z0-9_]{2,}", str(args.get("query") or ""))
    if not words:
        raise ValueError("query (words) or module is required")
    hits = [{k: r[k] for k in ("module", "area", "status", "tool", "tests", "lines", "about")}
            for r in cmap.find(m, words, int(args.get("limit") or 15))]
    unshipped = [h["module"] for h in hits if h["status"] != "product"]
    return _envelope(True, f"{len(hits)} HS modules match" + (f"; {len(unshipped)} not reached by any shipped entry point" if unshipped else ""),
                     {"matches": hits, "status_meaning": cmap.STATUS_MEANING},
                     boundary="A module's description is its author's claim; tests and reach are measured from the code.")


def _device_review(args, _project):
    from . import device_engineering, device_plan
    spec = args.get("spec")
    if spec is None and args.get("example"):
        examples = device_plan.example_specs()
        if args["example"] not in examples:
            raise ValueError(f"no example {args['example']!r}; examples: {', '.join(sorted(examples))}")
        spec = examples[args["example"]]
    if spec is None:
        raise ValueError("spec (a device spec) or example is required; examples: " + ", ".join(sorted(device_plan.example_specs())))
    res = device_engineering.build_engineering_review(spec)
    over = [c for d in res["domains"] for c in d["checks"] if c["status"] == device_engineering.EXCEEDS]
    counts = res["counts"]
    return _envelope(True, ", ".join(f"{v} {k}" for k, v in counts.items()), res,
                     problems=[f"{c['title']}: {c['summary']}" for c in over],
                     sources=[i.get("url") or i.get("source") or "" for i in res["sourced_inputs"] if i.get("url") or i.get("source")],
                     boundary=device_engineering.AUTHORITY)


def _identify_part(args, _project):
    from . import part_lookup
    res = part_lookup.lookup_part(args.get("marking"), int(args.get("limit") or part_lookup.MAX_MATCHES))
    problems = [] if res["matches"] else [res.get("reason") or "no KiCad library part matches this marking"]
    return _envelope(bool(res["matches"]), f"{len(res['matches'])} KiCad library parts for {res['query']}", res, problems=problems,
                     sources=[u for u in [(res.get("source") or {}).get("url")] if u],
                     boundary="A library name match, not an identification: confirm with the package, pin count and datasheet.")


def _battery_runtime(args, _project):
    from . import battery_runtime
    phases = [{"label": str(p.get("label") or f"phase {i + 1}"), "ma": float(p["ma"]), "seconds": float(p["seconds"]), "basis": "given"}
              for i, p in enumerate(args.get("phases") or [])]
    sd = args.get("self_discharge_pct_month")
    res = battery_runtime.runtime(float(args["capacity_mah"]), float(args["period_s"]), phases, float(args["sleep_ua"]),
                                  tuple(float(x) for x in sd) if sd else None)
    low, high = res["runtime_days"]["with_self_discharge"]
    return _envelope(True, f"average {res['average_ma']} mA; {low}-{high} days with self-discharge", res,
                     sources=[c["source"] for c in battery_runtime.CITED.values()], boundary=res["claim_boundary"])


def _prop_hover(args, project):
    from . import prop_static
    path = args.get("propdb_zip") or os.environ.get("HARDWARE_SPLICER_UIUC_PROPDB")
    if not path:
        raise ValueError("give propdb_zip or set HARDWARE_SPLICER_UIUC_PROPDB to the UIUC Propeller Database zip "
                         "(download from https://m-selig.ae.illinois.edu/props/propDB.html; it is not redistributed)")
    zip_path = Path(os.path.expanduser(str(path))) if not args.get("propdb_zip") else _readable(str(path), project)
    res = prop_static.hover(zip_path, str(args["prop"]), float(args["thrust_g"]))
    return _envelope(True, f"{res['prop']}: {res['rpm']} rpm, {res['shaft_power_w']} W shaft for {res['thrust_g']} g", res,
                     sources=["https://m-selig.ae.illinois.edu/props/propDB.html"], boundary=res["claim_boundary"])


def _plan_circuit(args, _project):
    """A bounded circuit topology from structured intent. The calling agent picks the planner, so HS makes no model call
    of its own (the model-first path would ask a paid provider); the planner is deterministic and blocks on missing facts."""
    from .circuit_synthesis import SynthesisCandidate, evaluate_topology_authority
    from .circuit_synthesis.semantic_planner_selector import PLANNER_REGISTRY, plan_circuit_from_semantic_selection
    from .intent_clarifier import analyze_intent_clarifications, apply_clarification_answers
    planner = str(args.get("planner") or "")
    if planner not in PLANNER_REGISTRY:
        raise ValueError("planner must be one of: " + "; ".join(f"{k} ({v['purpose']})" for k, v in PLANNER_REGISTRY.items()))
    intent = dict(args["intent"])
    clarifier = analyze_intent_clarifications(intent)
    trace = plan_circuit_from_semantic_selection(apply_clarification_answers(intent), {
        "selected_planner": planner, "rationale": str(args.get("rationale") or "chosen by the calling agent")})
    candidate = dict(trace.candidate or {})
    authority = evaluate_topology_authority(SynthesisCandidate.from_dict(candidate)) if candidate else None
    blocked = [c for c in candidate.get("constraints", []) if c.get("status") == "blocked"]
    problems = [f"{c.get('constraint_id')}: {c.get('requirement') or c.get('notes') or c.get('status')}" for c in blocked]
    problems += [f"missing evidence: {m}" for m in candidate.get("missing_evidence", []) if isinstance(m, str)]
    return _envelope(True, f"{planner}: {candidate.get('result')}, {len(candidate.get('selected_modules') or [])} modules, "
                     f"{len(blocked)} blocked constraints", {"candidate": candidate, "topology_authority": authority,
                                                              "clarifier": clarifier}, problems=problems,
                     boundary="A reviewable topology from catalogue contracts; it compiles nothing and authorizes no build "
                              "or power-on. Build it with hs_component_board or the catalogue compile path.")


def _native_function(module: str, function: str, kwargs: dict[str, Any], timeout: int = 1800) -> Any:
    """Call any HS function in the native interpreter through ``native_call`` (JSON in, JSON out)."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="hs-native-") as tmp:
        out = Path(tmp) / "result.json"
        run = subprocess.run([_native_python(), "-m", "hardware_splicer.native_call", f"hardware_splicer.{module}", function,
                              "--out", str(out)], input=json.dumps(kwargs), capture_output=True, text=True, timeout=timeout,
                             env={**os.environ, "PYTHONPATH": str(REPO / "src")}, cwd=str(REPO))
        if run.returncode != 0 or not out.is_file():
            # the exception line, not the whole traceback: that is what the agent can act on
            last = [line for line in run.stderr.strip().splitlines() if line.strip()][-1:] or ["no output"]
            raise RuntimeError(f"{module}.{function} failed: {last[0]}")
        return json.loads(out.read_text(encoding="utf-8"))


FEM_SUMMARY = ("status", "element_count", "node_count", "max_displacement_m", "max_von_mises_pa", "yield_safety_factor",
               "screening_verdict", "conservative", "screening_blockers", "warnings", "force_equilibrium_residual_n")


def _fem_screen(args, project):
    """Linear-elastic screening of one CAD part under one load case; the full field goes to the project, not the agent."""
    cad = _readable(str(args["cad_file"]), project)
    planes = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")
    if args["fixed_plane"] not in planes or args["loaded_plane"] not in planes:
        raise ValueError(f"fixed_plane and loaded_plane must be one of {', '.join(planes)}")
    force = [float(x) for x in args["force_n"]]
    if len(force) != 3:
        raise ValueError("force_n is [Fx, Fy, Fz] in newtons")
    common = {"path": str(cad), "stl_units": "mm" if cad.suffix.lower() == ".stl" else None,
              "fixed_plane": args["fixed_plane"], "loaded_plane": args["loaded_plane"], "total_force_n": force,
              "youngs_modulus_pa": float(args["youngs_pa"]), "poisson_ratio": float(args["poisson"]),
              "yield_strength_pa": float(args["yield_pa"]) if args.get("yield_pa") is not None else None}
    study = [float(x) for x in args.get("mesh_study_mm") or []]
    if study:
        res = _native_function("mechanical_cad_convergence", "run_cad_mesh_sensitivity", {**common, "mesh_sizes_mm": study})
        blockers = list(res.get("sensitivity_blockers") or []) + list(res.get("screening_blockers") or [])
        analysis = dict((res.get("levels") or [{}])[-1])  # the finest mesh
        analysis["yield_safety_factor"] = analysis.get("raw_yield_safety_factor")
    else:
        try:
            res = _native_function("mechanical_cad_fem", "run_cad_screening", {**common, "mesh_target_mm": float(args.get("mesh_size_mm") or 8.0)})
        except RuntimeError as exc:
            if "element count" in str(exc) or "node count" in str(exc):
                raise RuntimeError(f"{exc}. This bounded solver takes up to 5,000 elements and 2,000 nodes: screen one "
                                   "bracket, boss or plate cut from the part, or raise mesh_size_mm") from exc
            raise
        analysis = res.get("analysis") or {}
        blockers = list(res.get("screening_blockers") or [])
    full = None
    if project is not None:
        out = _project_path(project, "fem")
        full = out / f"{cad.stem}-{'study' if study else 'screen'}.json"
        full.write_text(json.dumps(res, indent=1, default=str))
    summary = {k: analysis.get(k) for k in FEM_SUMMARY if k in analysis}
    summary.update({"mesh_study": bool(study), "status": res.get("status"), "blockers": blockers,
                    "full_result": str(full.relative_to(project.root)) if full and project else None})
    sf = analysis.get("yield_safety_factor")
    problems = [f"blocker: {b}" for b in blockers]
    if isinstance(sf, (int, float)) and sf < float(args.get("min_safety_factor") or 2.0):
        problems.append(f"yield safety factor {sf:.2f} is under {float(args.get('min_safety_factor') or 2.0):g}")
    vm = analysis.get("max_von_mises_pa")
    return _envelope(True, f"peak von Mises {vm / 1e6:.2f} MPa" + (f", yield safety factor {sf:.2f}" if isinstance(sf, (int, float)) else "")
                     if isinstance(vm, (int, float)) else str(res.get("status")), summary, problems=problems,
                     boundary="Linear-elastic screening of one load case on the given material values; printed parts are "
                              "anisotropic and layer adhesion is weaker. Not a strength proof: test the part.")


def _arm_kinematics(args, project):
    """Typed arm proposal: reach and payload torque checks, a URDF on the project, and PyBullet FK/IK/workspace checks."""
    from . import robot_arm_design as rad, robot_arm_kinematics as rak
    proposal = rad.RobotArmDesignProposal.model_validate(dict(args["proposal"]))
    inventory, sources = [], []
    if args.get("supply_v") is not None and args.get("max_stall_share") is not None:
        # the same cited servos and usable share of stall torque hs_size_arm_actuators picks from
        from . import arm_actuator_sizing as aas
        share = float(args["max_stall_share"])
        for row in aas.cited_servo_rows(float(args["supply_v"])):
            inventory.append({"component_id": row["component_id"], "continuous_torque_nm": round(row["stall_torque_nm"] * share, 4),
                              "torque_basis": f"stall {row['stall_torque_nm']} N m x declared share {share:g}", "source": row["source"]})
            sources.append(row["source"])
    evaluation = rad.evaluate_robot_arm_design(proposal, requirements=dict(args.get("requirements") or {}), inventory=inventory)
    urdf = rak.generate_robot_arm_urdf(proposal, robot_name=str(args.get("name") or "hs_arm"))
    out = _project_path(project, "arm")
    urdf_path = out / f"{args.get('name') or 'hs_arm'}.urdf"
    urdf_path.write_text(urdf.text)
    physical_only = {"PHYSICAL_VALIDATION_REQUIRED"}  # only a build closes it: reported in the boundary, not left open
    problems = [f"{f.code}: {f.message}" for f in evaluation.findings if f.blocking and f.code not in physical_only]
    try:
        kin = _native_function("robot_arm_kinematics", "check_arm_proposal",
                               {"proposal": proposal.model_dump(mode="json"), "urdf_path": str(urdf_path)})
    except (RuntimeError, ValueError, OSError) as exc:  # no native interpreter: report, keep the static checks
        kin = {"status": "not_run", "reason": str(exc)}
        problems.append(f"kinematics not run: {exc}")
    if kin.get("status") not in ("pass", "not_run"):
        problems.append(f"kinematics: {kin.get('status')}")
    required = (args.get("requirements") or {}).get("required_reach_mm")
    sampled = kin.get("workspace_max_radius_m")
    closed = []
    if kin.get("status") == "pass" and required is not None and isinstance(sampled, (int, float)) and sampled * 1000 >= float(required):
        # the link-length sum is only an upper bound; PyBullet's sampled workspace is the measured reach on the proxy model
        problems = [p for p in problems if not p.startswith("WORKSPACE_NOT_VERIFIED")]
        closed.append(f"WORKSPACE_NOT_VERIFIED closed by PyBullet workspace sampling: {sampled * 1000:.0f} mm >= {float(required):g} mm")
    rel = str(urdf_path.relative_to(project.root))
    result = {"evaluation": {"status": evaluation.status, "summary": evaluation.summary,
                             "findings": [f.model_dump(mode="json") for f in evaluation.findings]},
              "kinematics": kin, "urdf": rel, "closed_by_kinematics": closed, "actuator_inventory": inventory,
              "next": f"hs_motion_sweep with urdf {rel} sweeps every joint for link collisions"}
    return _envelope(True, f"{len(proposal.joints)} joints, reach {sum(j.link_length_mm for j in proposal.joints):g} mm; "
                     f"evaluation {evaluation.status}, kinematics {kin.get('status')}", result, problems=problems, sources=sources,
                     boundary="Kinematics on proxy links only: masses, stiffness, transmission and real collision meshes are "
                              "not modelled, and nothing here authorizes motion.")


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
    ToolSpec("hs_project_link_design", "Link this objective to a stored machine project (HS's engineering design spine, saved "
             "through the product API): hs_project_status then shows the design's revision, achieved release state and "
             "release blockers beside the objective's own checks. Read-only on the design.",
             _obj({"design_project_id": {"type": "string"}}, ["project_id", "design_project_id"]), _project_link_design,
             category="research"),
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
    ToolSpec("hs_capability_search", "Search HS's own 600+ modules before building anything: each match's status (shipped, "
             "script-only, tests-only), tests and what it says it does; or give module to see what imports it and what it imports.",
             _obj({"query": {"type": "string"}, "module": {"type": "string"}, "limit": {"type": "integer"}}), _capability_search,
             category="research"),
    ToolSpec("hs_device_review", "Quantified review of a device plan (one microcontroller board, sensors, display, power, "
             "case): I2C bus, supply and power-bank runtime, thermal, antenna, mechanical fit and printing, every figure "
             "sourced or a listed assumption. Give spec, or example for a built-in device.",
             _obj({"spec": {"type": "object"}, "example": {"type": "string"}}), _device_review),
    ToolSpec("hs_identify_part", "Look a chip or module marking up in KiCad's ~20,000 library symbols (offline): exact, "
             "variant and family matches with datasheet links and default footprints. For salvaged boards.",
             _obj({"marking": {"type": "string"}, "limit": {"type": "integer"}}, ["marking"]), _identify_part, category="research"),
    ToolSpec("hs_battery_runtime", "How long a device that sleeps and wakes runs on a battery: average current from its "
             "phases (mA and seconds per wake-up) and sleep current, as a range with cited self-discharge.",
             _obj({"capacity_mah": {"type": "number"}, "period_s": {"type": "number"},
                   "phases": {"type": "array", "items": {"type": "object"}, "description": "[{label, ma, seconds}] per wake-up"},
                   "sleep_ua": {"type": "number"}, "self_discharge_pct_month": {"type": "array", "items": {"type": "number"}}},
                  ["capacity_mah", "period_s", "phases", "sleep_ua"]), _battery_runtime),
    ToolSpec("hs_prop_hover", "Static thrust and shaft power of a small propeller at a target thrust from the UIUC "
             "Propeller Database's measured coefficients (refuses to extrapolate past the measured range).",
             _obj({"prop": {"type": "string", "description": "UIUC name such as gwsdd_3x3"}, "thrust_g": {"type": "number"},
                   "propdb_zip": {"type": "string"}}, ["prop", "thrust_g"]), _prop_hover),
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
             "read-back parity and ERC; optionally the PCB (parts without pcb_xy are placed by HS by connectivity, steered by "
             "board.placement_hints; FreeRouted, re-routed until DRC and schematic parity pass, up to 3 tries), and fab files.",
             _obj({"design": {"type": "object"}, "stages": {"type": "array", "items": {"type": "string", "enum": ["schematic", "pcb", "fab"]}}},
                  ["project_id", "design"]), _component_board, check_key=lambda a: f"board:{(a.get('design') or {}).get('name')}"),
    ToolSpec("hs_plan_circuit", "Bounded circuit topology from structured intent (supply rails, loads, signals, allowed "
             "catalogue modules) with one of HS's deterministic planners: motor_driver, h_bridge, battery_power, power_rail, "
             "level_shift, analog_conditioning, sensor_interface, relay_switch. Missing ratings stay blockers.",
             _obj({"intent": {"type": "object", "description": "{goal, supply_rails, load_requirements, signal_requirements, "
                              "allowed_modules, required_evidence}"},
                   "planner": {"type": "string", "description": "motor_driver, h_bridge, battery_power, power_rail, "
                               "level_shift, analog_conditioning, sensor_interface or relay_switch",
                               "enum": ["motor_driver", "h_bridge", "battery_power", "power_rail", "level_shift",
                                                          "analog_conditioning", "sensor_interface", "relay_switch"]},
                   "rationale": {"type": "string"}}, ["intent", "planner"]), _plan_circuit,
             check_key=lambda a: f"circuit:{a.get('planner')}"),
    ToolSpec("hs_fem_screen", "Linear-elastic FEM screening of a STEP or STL part (from hs_rover_chassis or any CAD) for one "
             "load case: fixed face, loaded face, force, material; optional mesh study (3-4 decreasing sizes) for convergence. "
             "Returns peak stress, displacement and yield safety factor; the full field is saved on the project.",
             _obj({"cad_file": {"type": "string"}, "fixed_plane": {"type": "string", "enum": ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]},
                   "loaded_plane": {"type": "string", "enum": ["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]},
                   "force_n": {"type": "array", "items": {"type": "number"}, "description": "[Fx, Fy, Fz] N on the loaded face"},
                   "youngs_pa": {"type": "number"}, "poisson": {"type": "number"}, "yield_pa": {"type": "number"},
                   "mesh_size_mm": {"type": "number"}, "mesh_study_mm": {"type": "array", "items": {"type": "number"}},
                   "min_safety_factor": {"type": "number", "description": "default 2"}},
                  ["cad_file", "fixed_plane", "loaded_plane", "force_n", "youngs_pa", "poisson"]), _fem_screen,
             check_key=lambda a: f"fem:{a.get('cad_file')}"),
    ToolSpec("hs_arm_kinematics", "Check a typed robot-arm proposal (joints with axis, link length, limits, actuator): reach and "
             "payload torque against requirements, a URDF saved on the project, and PyBullet forward/inverse kinematics, "
             "workspace and self-collision. Feed the URDF to hs_motion_sweep.",
             _obj({"proposal": {"type": "object", "description": "{joints: [{joint_id, axis, link_length_mm, lower_limit_deg, "
                                "upper_limit_deg, actuator_part_id}], end_effector}"},
                   "requirements": {"type": "object", "description": "{required_reach_mm, payload_mass_kg, "
                                    "minimum_static_torque_safety_factor, max_joint_count}"},
                   "supply_v": {"type": "number", "description": "with max_stall_share: joints may name the cited servos "
                                "hs_size_arm_actuators picks (actuator_part_id)"},
                   "max_stall_share": {"type": "number"},
                   "name": {"type": "string"}}, ["project_id", "proposal"]), _arm_kinematics,
             check_key=lambda a: f"arm:{a.get('name') or 'hs_arm'}"),
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
    if project and name not in ("hs_project_open", "hs_project_record", "hs_project_status", "hs_project_link_design"):
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
