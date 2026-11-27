"""Does every part on a KiCad board resolve, at its distributor, to the part the board assumes?

    python -m hardware_splicer.distributor_check BOARD.net|BOARD.kicad_sch [--cache FILE] [--offline]

For each component with an LCSC code in its fields (LCSC, LCSC Part, JLCPCB, ...), the LCSC product record is fetched
and compared with the schematic:

* ``package_mismatch``: the footprint's package (0402, SOT-23-5, SOIC-8, QFN-56 ...) is not the record's package. The board
  would be assembled with a part that does not fit its pads, or ordered wrong.
* ``value_mismatch``: a resistor, capacitor or inductor value differs from the record's.
* ``code_not_found``: LCSC has no product under that code.
* ``out_of_stock`` (note) and ``mpn_differs`` (note: the schematic names another manufacturer part number).

Both sides are only compared where they parse into the same vocabulary; anything else is skipped, never guessed. The
record is a distributor's listing fetched at run time (cached), not a datasheet; stock changes daily.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

SCHEMA = "hardware_splicer.distributor_check.v1"
LCSC_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={code}"
CODE = re.compile(r"^C\d{1,9}$")
CODE_FIELDS = re.compile(r"^(lcsc|lcsc[ _#-]?(part|pn|no|number)?|jlc(pcb)?[ _#-]?(part|pn|no)?)$", re.I)
MPN_FIELDS = re.compile(r"^(mpn|partno|part ?number|manufacturer[ _]?part[ _]?(number|no)?|mfr[ _]?(pn|part))$", re.I)
IMPERIAL = ("01005", "0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512")
FAMILIES = re.compile(r"\b(SOT-?23(?:-\d)?L?|SOT-?223|SOT-?89(?:-\d)?|SOT-?323|SOT-?363|SC-?70(?:-\d)?|SC-?88|SOD-?\d{3}F?|SOIC-?\d+|SOP-?\d+|TSSOP-?\d+|MSOP-?\d+|"
                      r"[LVWU]?QFN-?\d+|[LVWU]?DFN-?\d+|[LT]QFP-?\d+|TO-?\d+|SMA|SMB|SMC)\b", re.I)


def _package(text: str) -> str | None:
    """A comparable package name: an imperial passive size, or a family with its pin count."""
    text = str(text or "")
    size = re.search(r"(?<!\d)(" + "|".join(IMPERIAL) + r")(?!\d)", text)
    if size and re.search(r"(^|[:_ ])(R|C|L|D|LED|FB|F)_|resistor|capacitor|inductor|chip|^\d{4}$", text, re.I):
        return size.group(1)
    family = FAMILIES.search(text.replace("_", "-").replace(" ", "-"))
    if not family:
        return size.group(1) if size and text.strip() == size.group(1) else None
    name = family.group(1).upper().replace("--", "-")
    name = re.sub(r"^([A-Z]+)-?(\d)", r"\1-\2", name)                # SOT23 -> SOT-23, SOIC8 -> SOIC-8
    name = re.sub(r"^[LVWU](QFN|DFN)", r"\1", name)                   # LQFN/VQFN/WQFN are QFN outlines; pins decide
    name = re.sub(r"^(SOP)-", "SOIC-", name)                          # LCSC writes SOP-8 for the SOIC-8 outline
    # One outline, several names: LCSC writes SOT-23-6L, SC-70-6 and SC-88 for SOT-23-6 and SOT-363.
    name = re.sub(r"^(SOT-23(?:-\d)?)L$", r"\1", name)
    return {"SOT-23-3": "SOT-23", "SC-70-6": "SOT-363", "SC-88": "SOT-363", "SC-70": "SOT-323", "SC-70-3": "SOT-323",
            "SOT-89-3": "SOT-89"}.get(re.sub(r"^(SOD-\d{3})F$", r"\1", name), re.sub(r"^(SOD-\d{3})F$", r"\1", name))


_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "R": 1.0}


def _value(text: str, unit: str) -> float | None:
    """10k, 4k7, 5.1kΩ, 100nF, 0.1u, 1uF, 4.7uH, 10R, 0R -> a number in base units."""
    text = str(text or "").replace("Ω", "").replace("ohm", "").replace("Ohm", "").replace("μ", "u").replace("µ", "u").strip()
    text = re.sub(r"(\d)\s+([pnumkKMRFH])", r"\1\2", text)  # "22 uF", "100 nF": KiCad values often have a space
    text = re.split(r"[\s/,]", text)[0] if text else ""
    tail = f"(?:{unit})?" if unit else ""
    m = re.fullmatch(r"(\d+)([pnuµmkKMR])(\d+)" + tail, text)  # 4k7, 2u2, 4R7
    if m:
        return float(f"{m.group(1)}.{m.group(3)}") * _SI[m.group(2)]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([pnuµmkKMR]?)" + tail, text)
    if m and m.group(2) in _SI:
        return float(m.group(1)) * _SI[m.group(2)]
    return None


def _kind(ref: str) -> tuple[str, str] | None:
    for prefix, param, unit in (("R", "Resistance", ""), ("C", "Capacitance", "F"), ("L", "Inductance", "H")):
        if re.fullmatch(prefix + r"\d+", ref):
            return param, unit
    return None


def lcsc_fetcher(cache_path: Path | None = None, offline: bool = False, delay: float = 0.6) -> Callable[[str], dict | None]:
    """Fetch LCSC product records by code, caching each one; offline uses the cache only."""
    cache: dict[str, Any] = json.loads(cache_path.read_text()) if cache_path and cache_path.is_file() else {}
    last = [0.0]

    def fetch(code: str) -> dict | None:
        if code in cache:
            return cache[code]
        if offline:
            return None
        wait = delay - (time.monotonic() - last[0])
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(LCSC_URL.format(code=code), headers={"User-Agent": "hardware-splicer-part-check"})
        with urllib.request.urlopen(request, timeout=30) as reply:  # noqa: S310 - fixed https host
            body = json.loads(reply.read().decode("utf-8"))
        last[0] = time.monotonic()
        result = body.get("result") or {}
        record = {"code": code, "found": bool(result.get("productModel")), "model": result.get("productModel"),
                  "package": result.get("encapStandard"), "name": result.get("productNameEn"), "stock": result.get("stockNumber"),
                  "params": {p.get("paramNameEn"): p.get("paramValueEn") for p in result.get("paramVOList") or [] if p.get("paramNameEn")},
                  "fetched": time.strftime("%Y-%m-%d")}
        cache[code] = record
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=0, ensure_ascii=False))
        return record

    return fetch


def check_components(components: dict[str, dict[str, Any]], fetch: Callable[[str], dict | None]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checked = skipped = 0

    def finding(severity, rule, ref, message, record):
        findings.append({"severity": severity, "rule": rule, "components": [ref], "message": message,
                         "basis": f"LCSC product record {record['code']} ({record.get('model')}), fetched {record.get('fetched')}"})

    for ref, comp in sorted(components.items()):
        fields = comp.get("fields", {})
        code = next((v.strip() for k, v in fields.items() if CODE_FIELDS.match(k.strip()) and CODE.match(v.strip())), None)
        if code is None:
            skipped += 1
            continue
        record = fetch(code)
        if record is None:
            skipped += 1
            continue
        checked += 1
        if not record.get("found"):
            finding("warning", "code_not_found", ref, f"{ref}: LCSC has no product {code}. The part cannot be ordered under this code.", record)
            continue
        ours, theirs = _package(comp.get("footprint", "")), _package(record.get("package", ""))
        named = _package(record.get("name") or "")
        if ours and theirs and ours != theirs and named and named != theirs:
            # The listing contradicts itself (C552486: package SC-70, name "... SOT-23"): report it, do not judge the board on it.
            finding("info", "listing_inconsistent", ref, f"{ref}: {code} lists package {record.get('package')} but its name says {named}; "
                    f"the footprint is {ours}. Check the datasheet.", record)
        elif ours and theirs and ours != theirs:
            finding("error", "package_mismatch", ref,
                    f"{ref}: footprint {comp.get('footprint')} is {ours}, but {code} ({record.get('model')}) is {record.get('package')}. "
                    "The part will not fit the pads.", record)
        kind = _kind(ref)
        if kind:
            param, unit = kind
            want, have = _value(comp.get("value", ""), unit), _value(record.get("params", {}).get(param, ""), unit)
            if want is not None and have is not None and not math.isclose(want, have, rel_tol=0.011, abs_tol=1e-15):
                finding("error", "value_mismatch", ref,
                        f"{ref}: the schematic says {comp.get('value')}, but {code} is {record['params'][param]} ({record.get('name')}).", record)
        if record.get("stock") == 0:
            finding("info", "out_of_stock", ref, f"{ref}: {code} ({record.get('model')}) shows 0 in stock at LCSC.", record)
        mpn = next((v.strip() for k, v in fields.items() if MPN_FIELDS.match(k.strip()) and v.strip()), None)
        if mpn and record.get("model") and re.sub(r"[^A-Z0-9]", "", mpn.upper())[:8] != re.sub(r"[^A-Z0-9]", "", record["model"].upper())[:8]:
            finding("info", "mpn_differs", ref, f"{ref}: the schematic names {mpn}; {code} is {record['model']}. Fine if it is an approved equivalent.", record)
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("error", "warning", "info")}
    return {"schema_version": SCHEMA, "parts_with_codes": checked, "parts_without_codes": skipped, "findings": findings, "counts": counts,
            "claim_boundary": "Compares the schematic with LCSC's product listing; a listing is not a datasheet, and only parsed packages and "
                              "R/C/L values are compared."}


def check_netlist(path: Path, fetch: Callable[[str], dict | None]) -> dict[str, Any]:
    from .kicad_design_review import parse_netlist, review_schematic  # noqa: F401 - review_schematic exports .kicad_sch

    if path.suffix == ".net":
        model = parse_netlist(path.read_text(encoding="utf-8", errors="replace"))
    else:
        import subprocess
        import tempfile

        from .model3d import resolve_kicad_cli

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "board.net"
            subprocess.run([resolve_kicad_cli() or "kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "--output", str(out), str(path)],
                           capture_output=True, timeout=300, check=False)
            model = parse_netlist(out.read_text(encoding="utf-8", errors="replace"))
    return check_components(model["components"], fetch)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache, args = Path(args[i + 1]), args[:i] + args[i + 2:]
    offline = "--offline" in args
    args = [a for a in args if a != "--offline"]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps(check_netlist(Path(args[0]), lcsc_fetcher(cache, offline)), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
