"""Evidence-typed PC refurbishment casefile.

Reads one ``unit.json`` plus the bench bundle(s) written by ``bench_collect.py``,
parses the RAW tool output (smartctl JSON, memtester, dmidecode, thermal samples)
into gates, and reports a decision. Design rules, all enforced by tests:

* Unknown is not pass. A missing file, tool or measurement leaves the gate ``unknown``.
* Every gate carries an authority: ``instrument_log`` (parsed from hash-checked raw
  tool output), ``operator_attested`` (a human said so, with an evidence file) or
  ``none``. Operator checklists can never be upgraded to instrument evidence.
* This module never *releases* a unit. The best it can say alone is
  ``READY_FOR_INDEPENDENT_REVIEW``. ``APPROVED_FOR_SALE`` additionally needs a review
  record by a different person that names the sha256 of the bench manifest, and the
  owner's own legal confirmations. The module verifies that binding; it does not
  supply the judgement.
* ``control_host``, ``fixture`` and ``public_case`` roles can never release.
* Hash checks detect tampering and mix-ups, not a dishonest operator. This is an
  honest-operator workflow tool, not an anti-fraud system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hs.pc_refurb_casefile.v1"
NON_PRODUCT_ROLES = ("control_host", "fixture", "public_case")

POLICY: dict[str, Any] = {
    "memtest_min_coverage": 0.75, "memtest_min_loops": 2,
    "stress_min_seconds": 1200, "max_temp_c": 95.0,
    "ata_zero_attrs": (5, 187, 197, 198), "ata_max_crc_errors": 50,
    "nvme_max_percentage_used": 80, "nvme_min_available_spare": 20,
    "advisory_power_on_hours": 40000,
    "wipe_min_entropy_bits": 7.5,
    "identity_tolerance": 0.10,
}
# smartctl exit_status bits: 8 failing, 16 prefail<=thr, 128 self-test log errors => fail.
SMART_FAIL_BITS = 8 | 16 | 128
SMART_CMD_BITS = 1 | 2 | 4  # command line / open failed / SMART command failed => unreliable
DMESG_FATAL = re.compile(r"machine check|hardware error|mce:|i/o error|ata\d+.*(?:failed|error)|"
                         r"nvme.*(?:timeout|reset|abort)|ext4-fs error|critical medium error|"
                         r"thermal.*(?:shutdown|critical)|memory corruption|edac.*(?:uncorrect|ue)", re.I)
REQUIRED_RIGHTS = ("title_transfer_document", "seller_identity_recorded", "data_owner_release")
REQUIRED_CHECKLIST = ("usb_ports_all_tested", "video_output", "power_button_and_front_panel",
                      "fans_and_cleaning_done", "cosmetic_grade_photos")
OWNER_LEGAL_ITEMS = ("second_hand_trade_licence_status_confirmed", "tax_registration_status_confirmed",
                     "return_and_warranty_terms_written", "os_licence_disclosure_written")


# ------------------------------------------------------------------ results
def gate(name: str, status: str, authority: str, detail: str, evidence: list[str] | None = None, **extra) -> dict:
    assert status in ("pass", "fail", "unknown", "not_applicable")
    return {"gate": name, "status": status, "authority": authority, "detail": detail,
            "evidence": evidence or [], **extra}


def unknown(name: str, why: str) -> dict:
    return gate(name, "unknown", "none", why)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ bundle
class BundleError(Exception):
    pass


def load_bundle(d: Path) -> dict:
    """Load a bench bundle and verify every file against manifest.json."""
    mp = d / "manifest.json"
    if not mp.is_file():
        raise BundleError(f"{d}: no manifest.json")
    man = json.loads(mp.read_text())
    if man.get("schema") != "hs.pc_bench_bundle.v1":
        raise BundleError(f"{d}: unknown bundle schema {man.get('schema')!r}")
    bad = []
    for name, digest in man["files_sha256"].items():
        p = d / name
        if not p.resolve().is_relative_to(d.resolve()) or not p.is_file() or sha256(p) != digest:
            bad.append(name)
    if bad:
        raise BundleError(f"{d}: files missing or modified since collection: {bad}")
    extra = sorted(f.name for f in d.iterdir() if f.is_file() and f.name not in man["files_sha256"]
                   and f.name != "manifest.json")
    return {"dir": d, "manifest": man, "manifest_sha256": sha256(mp), "unlisted_files": extra}


def read(b: dict, name: str) -> str | None:
    p = b["dir"] / name
    if not p.is_file():
        return None
    t = p.read_text(errors="replace")
    return None if t.startswith("# HS_FAILED") else t


def read_json(b: dict, name: str) -> Any | None:
    t = read(b, name)
    try:
        return json.loads(t) if t else None
    except ValueError:
        return None


# ------------------------------------------------------------------ parsers
def parse_dmi(text: str) -> dict:
    """Parse dmidecode blocks into {system, baseboard, processors[], dimms[]}."""
    out: dict[str, Any] = {"processors": [], "dimms": []}
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip() and not l.startswith(("#", "Handle", "Getting", "SMBIOS"))]
        if not lines:
            continue
        title, kv = lines[0].strip(), {}
        for l in lines[1:]:
            if ":" in l and not l.startswith("\t\t"):
                k, v = l.split(":", 1)
                kv[k.strip()] = v.strip()
        if title == "System Information":
            out["system"] = {k: kv.get(k) for k in ("Manufacturer", "Product Name", "Version")}
        elif title == "Base Board Information":
            out["baseboard"] = {k: kv.get(k) for k in ("Manufacturer", "Product Name")}
        elif title == "BIOS Information":
            out["bios"] = {k: kv.get(k) for k in ("Vendor", "Version", "Release Date")}
        elif title == "Processor Information":
            out["processors"].append(kv.get("Version") or kv.get("Family"))
        elif title == "Memory Device":
            m = re.match(r"(\d+)\s*(MB|GB)", kv.get("Size", ""))
            out["dimms"].append({"size_mb": int(m.group(1)) * (1024 if m.group(2) == "GB" else 1) if m else 0,
                                 "type": kv.get("Type"), "speed": kv.get("Speed"), "locator": kv.get("Locator")})
    return out


def parse_cpuinfo(text: str) -> dict:
    m = re.search(r"model name\s*:\s*(.+)", text)
    return {"model": m.group(1).strip() if m else None, "threads": len(re.findall(r"^processor\s*:", text, re.M))}


def total_ram_mb(meminfo: str) -> int | None:
    m = re.search(r"MemTotal:\s+(\d+)", meminfo or "")
    return int(m.group(1)) // 1024 if m else None


def internal_disks(lsblk: dict) -> list[dict]:
    return [d for d in lsblk.get("blockdevices", []) if d.get("type") == "disk"]


def eval_smart(j: dict, size_bytes: int | None = None) -> tuple[str, str, dict]:
    """Return (status, detail, facts) for one smartctl -a -j document."""
    if not isinstance(j, dict) or j.get("hs_status") in ("tool_missing", "unparseable"):
        return "unknown", f"smartctl output unavailable ({(j or {}).get('hs_status')})", {}
    sc = j.get("smartctl", {})
    exit_status = int(sc.get("exit_status", 0))
    facts: dict[str, Any] = {"model": j.get("model_name"), "smartctl_exit_status": exit_status,
                             "power_on_hours": (j.get("power_on_time") or {}).get("hours")}  # NOT attr 9 raw: packed on Seagate
    problems: list[str] = []
    nv = j.get("nvme_smart_health_information_log")
    # critical_warning bit 1 (value 2) alone = composite temperature crossed its threshold. That is a
    # transient thermal state, not a media fault: smartctl also sets "disk failing" and passed=false for it.
    # Treat it as "retest after cooling" (unknown, still blocks release), unless a real fault bit is also set.
    temp_flag_only = bool(nv) and nv.get("critical_warning") == 2
    if exit_status & SMART_CMD_BITS:
        return "unknown", f"smartctl could not read the device reliably (exit_status={exit_status})", facts
    fail_bits = exit_status & SMART_FAIL_BITS
    if temp_flag_only:
        fail_bits &= ~8
    if fail_bits:
        problems.append(f"smartctl exit_status={exit_status} reports failing/prefail/self-test errors")
    ss = j.get("smart_status", {})
    if ss.get("passed") is False and not temp_flag_only:
        problems.append("overall SMART health: FAILED")
    elif "passed" not in ss:
        return "unknown", "no overall SMART verdict in output", facts
    if nv:
        facts.update({k: nv.get(k) for k in ("critical_warning", "percentage_used", "available_spare", "media_errors",
                                             "warning_temp_time", "critical_comp_time", "temperature")})
        if nv.get("critical_warning") and not temp_flag_only:
            problems.append(f"NVMe critical_warning={nv['critical_warning']}")
        if nv.get("media_errors"):
            problems.append(f"NVMe media_errors={nv['media_errors']}")
        if nv.get("percentage_used", 0) > POLICY["nvme_max_percentage_used"]:
            problems.append(f"NVMe wear {nv['percentage_used']}% used")
        if nv.get("available_spare", 100) < POLICY["nvme_min_available_spare"]:
            problems.append(f"NVMe spare {nv['available_spare']}%")
        if temp_flag_only and not problems:
            return "unknown", (f"NVMe temperature flag set at {nv.get('temperature')} C (cumulative minutes over warning "
                               f"{nv.get('warning_temp_time')}, over critical {nv.get('critical_comp_time')}): transient; let "
                               "the drive cool and re-run. Cumulative over-temperature time is a wear indicator to disclose."), facts
    table = (j.get("ata_smart_attributes") or {}).get("table")
    if table:
        raw = {a["id"]: a["raw"]["value"] for a in table}
        facts["ata"] = {i: raw.get(i) for i in (5, 187, 188, 197, 198, 199) if i in raw}
        for i in POLICY["ata_zero_attrs"]:
            if raw.get(i, 0) != 0:
                problems.append(f"ATA attribute {i} raw={raw[i]} (policy: must be 0)")
        if raw.get(199, 0) > POLICY["ata_max_crc_errors"]:
            problems.append(f"UDMA CRC errors={raw[199]} (cable/controller)")
    if not nv and not table:
        return "unknown", "no NVMe or ATA health attributes in output", facts
    return ("fail", "; ".join(problems), facts) if problems else ("pass", "SMART healthy per policy", facts)


def eval_memory(meta: dict | None, text: str | None) -> dict:
    if not meta or meta.get("hs_status") != "ran":
        return unknown("memory_test", "memtester was not run on this unit")
    out, cov = text or "", meta["tested_mb"] / max(1, meta["total_mb"])
    ev = ["memtester.meta.json", "memtester.txt"]
    if meta.get("rc") != 0 or re.search(r"FAILURE|failed", out, re.I):
        return gate("memory_test", "fail", "instrument_log", f"memtester rc={meta.get('rc')} / FAILURE in output", ev)
    if meta.get("loops", 0) < POLICY["memtest_min_loops"] or cov < POLICY["memtest_min_coverage"]:
        return unknown("memory_test", f"clean but insufficient: loops={meta.get('loops')} (need "
                       f"{POLICY['memtest_min_loops']}), coverage={cov:.0%} (need {POLICY['memtest_min_coverage']:.0%})")
    return gate("memory_test", "pass", "instrument_log",
                f"{meta['loops']} loops over {meta['tested_mb']} MiB ({cov:.0%} of RAM), rc=0", ev)


def eval_thermal(t: dict | None) -> dict:
    if not t or t.get("hs_status") != "ran":
        return unknown("thermal_stress", "stress-ng was not run on this unit")
    ev = ["thermal.json", "stress.txt"]
    peak = max((v for s in t["samples"] for v in s["temps_c"].values()), default=None)
    thr = {k: t["throttle_after"].get(k, 0) - t["throttle_before"].get(k, 0) for k in t["throttle_after"]}
    thr = {k: v for k, v in thr.items() if v}
    if t.get("rc") != 0:
        return gate("thermal_stress", "fail", "instrument_log", f"stress-ng rc={t.get('rc')} (crash/hang/oom)", ev)
    if t["wall_seconds"] < POLICY["stress_min_seconds"]:
        return unknown("thermal_stress", f"ran {t['wall_seconds']}s, need {POLICY['stress_min_seconds']}s")
    if peak is None:
        return unknown("thermal_stress", "no temperature sensors readable; cannot judge thermals")
    if peak > POLICY["max_temp_c"]:
        return gate("thermal_stress", "fail", "instrument_log", f"peak {peak:.0f} C > {POLICY['max_temp_c']:.0f} C "
                    "(route: clean, repaste, re-run)", ev)
    if thr:
        return gate("thermal_stress", "fail", "instrument_log", f"thermal throttle events {thr} (route: clean, repaste, re-run)", ev)
    return gate("thermal_stress", "pass", "instrument_log", f"{t['wall_seconds']}s load, peak {peak:.0f} C, no throttling", ev)


# ------------------------------------------------------------------ evaluation
def rights_gates(unit: dict, root: Path) -> list[dict]:
    out = []
    for key in REQUIRED_RIGHTS:
        row = (unit.get("rights") or {}).get(key) or {}
        p = (root / row["evidence"]) if isinstance(row.get("evidence"), str) else None
        if p and p.resolve().is_relative_to(root.resolve()) and p.is_file() and p.stat().st_size > 0:
            out.append(gate("rights:" + key, "pass", "operator_attested",
                            "evidence file present (authenticity not machine-verifiable)", [row["evidence"]],
                            evidence_sha256=sha256(p)))
        else:
            out.append(unknown("rights:" + key, "no non-empty evidence file"))
    return out


def identity_gate(unit: dict, dmi: dict, cpu: dict, ram_mb: int | None, disks: list[dict]) -> dict:
    claimed = unit.get("claimed") or {}
    if not claimed:
        return gate("identity_matches_claim", "not_applicable", "none", "no seller claim recorded")
    tol, mism = POLICY["identity_tolerance"], []
    c = claimed.get("cpu")
    seen_cpu = " ".join(filter(None, [cpu.get("model")] + dmi.get("processors", [])))
    if c and c.lower().replace(" ", "") not in seen_cpu.lower().replace(" ", ""):
        mism.append(f"CPU claimed {c!r}, observed {seen_cpu.strip()!r}")
    if claimed.get("ram_gb") and ram_mb and abs(ram_mb / 1024 - claimed["ram_gb"]) > claimed["ram_gb"] * tol + 0.6:
        mism.append(f"RAM claimed {claimed['ram_gb']} GB, observed {ram_mb/1024:.1f} GB")
    if claimed.get("storage_gb") and disks:
        total = sum(d["size"] for d in disks) / 1e9
        if abs(total - claimed["storage_gb"]) > claimed["storage_gb"] * (tol + 0.08):
            mism.append(f"storage claimed {claimed['storage_gb']} GB, observed {total:.0f} GB")
    if mism:
        return gate("identity_matches_claim", "fail", "instrument_log", "; ".join(mism), ["cpuinfo.txt", "dmidecode.txt"])
    return gate("identity_matches_claim", "pass", "instrument_log", "observed hardware agrees with seller claim",
                ["cpuinfo.txt", "dmidecode.txt", "meminfo.txt", "lsblk.json"])


def wipe_gates(unit_root: Path, unit: dict, disks: list[dict]) -> list[dict]:
    wipes = []
    for rel in (unit.get("bundles") or {}).get("wipe", []):
        try:
            wb = load_bundle(unit_root / rel)
        except BundleError as e:
            return [gate("storage_sanitized", "fail", "instrument_log", f"wipe bundle invalid: {e}")]
        for f in wb["manifest"]["files_sha256"]:
            if f.startswith("wipe_"):
                wipes.append((json.loads((wb["dir"] / f).read_text()), f"{rel}/{f}"))
    out = []
    for d in disks:
        match = [w for w, _ in wipes if w["size_bytes"] == d["size"]]
        name = f"storage_sanitized:{d['name']}"
        if not match:
            out.append(unknown(name, "no verify-wipe bundle for this disk (sanitization is a separate human-authorised step)"))
            continue
        w, ev = match[-1], [e for x, e in wipes if x is match[-1]]
        if w.get("signature_tool") != "ok":
            out.append(unknown(name, "wipefs signature check unavailable"))
        elif json.loads(w["signatures_stdout"] or '{"signatures": []}').get("signatures"):
            out.append(gate(name, "fail", "instrument_log", "filesystem/partition signatures still present", ev))
        elif w["operator_declared_method"] == "unspecified":
            out.append(unknown(name, "no sanitization method declared (HS_WIPE_METHOD)"))
        elif w["sampled_blocks"] and (w["zero_blocks"] == w["sampled_blocks"]
                                      or w["min_entropy_bits_per_byte"] >= POLICY["wipe_min_entropy_bits"]):
            out.append(gate(name, "pass", "instrument_log",
                            f"no signatures; {w['sampled_blocks']} sampled blocks zero/random; method={w['operator_declared_method']}. "
                            "Sampling detects an unwiped disk; it cannot prove unread sectors.", ev))
        else:
            out.append(gate(name, "fail", "instrument_log", "sampled blocks still contain structured data", ev))
    return out


def evaluate(unit_path: Path) -> dict:
    unit_path = unit_path.resolve()
    root = unit_path.parent
    unit = json.loads(unit_path.read_text())
    role = unit.get("role", "target")
    gates: list[dict] = [] + rights_gates(unit, root)
    bench = None
    try:
        rel = (unit.get("bundles") or {}).get("bench")
        bench = load_bundle(root / rel) if rel else None
    except BundleError as e:
        gates.append(gate("bench_bundle_integrity", "fail", "instrument_log", str(e)))
    facts: dict[str, Any] = {}
    if bench is None:
        if not any(g["gate"] == "bench_bundle_integrity" for g in gates):
            gates.append(unknown("bench_bundle", "no bench bundle supplied"))
    else:
        man = bench["manifest"]
        if man.get("role") != role:
            gates.append(gate("bench_role_matches_unit", "fail", "instrument_log",
                              f"bundle role {man.get('role')!r} != unit role {role!r}"))
        if bench["unlisted_files"]:
            gates.append(gate("bench_bundle_integrity", "fail", "instrument_log",
                              f"files present but not in manifest: {bench['unlisted_files']}"))
        dmi = parse_dmi(read(bench, "dmidecode.txt") or "")
        cpu = parse_cpuinfo(read(bench, "cpuinfo.txt") or "")
        ram_mb = total_ram_mb(read(bench, "meminfo.txt") or "")
        lsblk = read_json(bench, "lsblk.json") or {"blockdevices": []}
        all_disks = internal_disks(lsblk)
        disks = [d for d in all_disks if d.get("tran") != "usb"]
        facts.update({"system": dmi.get("system"), "bios": dmi.get("bios"), "cpu": cpu, "ram_total_mb": ram_mb,
                      "dimms": dmi["dimms"], "excluded_usb_disks": len(all_disks) - len(disks),
                      "host_fingerprint": man.get("host_fingerprint"), "bench_manifest_sha256": bench["manifest_sha256"]})
        gates.append(identity_gate(unit, dmi, cpu, ram_mb, disks))
        err = read(bench, "dmesg_err.txt")
        hits = [l for l in (err or "").splitlines() if DMESG_FATAL.search(l)]
        gates.append(unknown("boot_and_kernel_health", "dmesg capture unavailable") if err is None else
                     gate("boot_and_kernel_health", "fail" if hits else "pass", "instrument_log",
                          f"{len(hits)} fatal kernel messages, e.g. {hits[0][:120]!r}" if hits else
                          "booted a live OS on this unit; no machine-check/I-O/ATA/NVMe fatal errors logged", ["dmesg_err.txt"]))
        gates.append(eval_memory(read_json(bench, "memtester.meta.json"), read(bench, "memtester.txt")))
        gates.append(eval_thermal(read_json(bench, "thermal.json")))
        if not disks:
            gates.append(gate("storage_health", "not_applicable", "instrument_log",
                              "no internal disk: completion must add storage (cost goes in the economics)"))
        for d in disks:
            j = read_json(bench, f"smart_{d['name']}.json")
            st, detail, f = eval_smart(j, d["size"])
            facts.setdefault("disks", {})[d["name"]] = {"size_bytes": d["size"], **f}
            gates.append(gate(f"storage_health:{d['name']}", st, "instrument_log" if st != "unknown" else "none",
                              detail, [f"smart_{d['name']}.json"]))
        gates.extend(wipe_gates(root, unit, disks))
        net = read_json(bench, "ip_addr.json") or []
        up = [i for i in net if isinstance(i, dict) and i.get("ifname") != "lo" and i.get("operstate") == "UP"
              and any(a.get("family") == "inet" for a in i.get("addr_info", []))]
        gates.append(gate("network", "pass" if up else "unknown", "instrument_log" if up else "none",
                          f"{len(up)} interface(s) UP with an IPv4 address (DHCP)" if up else
                          "no UP interface with an address; plug a cable and re-run", ["ip_addr.json"]))
    chk = unit.get("operator_checklist") or {}
    for k in REQUIRED_CHECKLIST:
        row = chk.get(k) or {}
        gates.append(gate("checklist:" + k, "pass" if row.get("pass") is True else
                          ("fail" if row.get("pass") is False else "unknown"), "operator_attested" if "pass" in row else "none",
                          row.get("note", "not recorded")))
    lic = unit.get("licence") or {}
    ok_lic = lic.get("os_to_ship") in ("linux", "none") or (lic.get("os_to_ship") == "windows_with_coa" and lic.get("coa_photo"))
    gates.append(gate("os_licence", "pass" if ok_lic else "unknown", "operator_attested" if ok_lic else "none",
                      f"ships with: {lic.get('os_to_ship')}" if ok_lic else
                      "decide: linux / no OS / Windows only with the original COA photographed"))
    return decide(unit, role, gates, facts, bench, root)


def decide(unit: dict, role: str, gates: list[dict], facts: dict, bench: dict | None, root: Path) -> dict:
    fails = [g for g in gates if g["status"] == "fail"]
    unk = [g for g in gates if g["status"] == "unknown"]
    acquired = unit.get("acquired") is True
    if role in NON_PRODUCT_ROLES:
        status, why = f"NOT_A_PRODUCT_{role.upper()}", f"role {role!r} can never release a product"
    elif not acquired:
        status, why = "PRE_ACQUISITION", "unit not acquired: nothing here is physical evidence about a unit we own"
    elif any(g["gate"].startswith("identity") for g in fails):
        status, why = "DISPUTE_CLAIM_MISMATCH", "observed hardware contradicts the seller claim: do not accept at the quoted price"
    elif fails:
        status, why = "REJECT_OR_REPAIR", "hard fail on " + ", ".join(g["gate"] for g in fails)
    elif unk:
        status, why = "BLOCKED_MISSING_EVIDENCE", f"{len(unk)} gate(s) unknown"
    else:
        status, why = "READY_FOR_INDEPENDENT_REVIEW", "all gates pass; a human second reader must still approve"
    approved, review_note = False, None
    rev, legal = unit.get("review") or {}, unit.get("owner_legal_confirmations") or {}
    if status == "READY_FOR_INDEPENDENT_REVIEW":
        want = bench["manifest_sha256"] if bench else None
        if not rev:
            review_note = "no review record"
        elif rev.get("reviewer") in (None, "", (unit.get("operator") or {}).get("name")):
            review_note = "reviewer must be a different person from the operator"
        elif rev.get("covers_manifest_sha256") != want:
            review_note = "review does not cover this bench manifest (stale or wrong bundle)"
        elif not all(legal.get(k) is True for k in OWNER_LEGAL_ITEMS):
            review_note = "owner legal confirmations incomplete: " + ", ".join(k for k in OWNER_LEGAL_ITEMS if legal.get(k) is not True)
        else:
            approved, status, why = True, "APPROVED_FOR_SALE", "independent review bound to this manifest + owner legal items confirmed"
    auth: dict[str, int] = {}
    for g in gates:
        auth[g["authority"]] = auth.get(g["authority"], 0) + 1
    return {"schema": SCHEMA, "unit_id": unit.get("unit_id"), "lot_id": unit.get("lot_id"), "role": role,
            "acquired": acquired, "decision": status, "reason": why, "review_note": review_note,
            "approved_for_sale": approved, "gates": gates, "authority_counts": auth, "facts": facts,
            "policy": {k: list(v) if isinstance(v, tuple) else v for k, v in POLICY.items()},
            "physical_proof": ("NONE: role/acquisition state forbids physical claims" if status.startswith(("NOT_A", "PRE_"))
                               else "instrument logs from this unit's bench bundle; see gate authority"),
            "partout_candidates": partout_candidates(gates, facts)}


def partout_candidates(gates: list[dict], facts: dict) -> list[dict]:
    """Components whose OWN gate passed, usable even when the whole machine fails."""
    by = {g["gate"]: g for g in gates}
    out = []
    if by.get("memory_test", {}).get("status") == "pass":
        for d in facts.get("dimms", []):
            if d["size_mb"]:
                out.append({"asset_type": "ram_module", "name": f"{d['size_mb']//1024} GB {d['type']} {d['speed']}",
                            "evidence_gate": "memory_test"})
    for k, g in by.items():
        if k.startswith("storage_health:") and g["status"] == "pass" and \
                by.get("storage_sanitized:" + k.split(":", 1)[1], {}).get("status") == "pass":
            out.append({"asset_type": "storage", "name": facts["disks"][k.split(":", 1)[1]].get("model"),
                        "evidence_gate": k})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate a PC refurbishment casefile (never releases on its own)")
    ap.add_argument("unit", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    rep = evaluate(a.unit)
    text = json.dumps(rep, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
    print(f"{rep['unit_id']}: {rep['decision']} — {rep['reason']}")
    for g in rep["gates"]:
        print(f"  {g['status']:<14}{g['authority']:<18}{g['gate']}: {g['detail'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
