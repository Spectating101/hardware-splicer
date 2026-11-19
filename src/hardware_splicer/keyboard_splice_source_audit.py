"""Independent schematic/PCB/firmware checks for an older KiCad keyboard source.

Input sources must come from the exact upstream repository revision, verified
against pinned SHA-256s. The tool does NOT imply source DRC passed, firmware was
compiled, or any real controller/USB/keypad was powered.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def legacy_netlist_nodes(text: str) -> dict[str, list[tuple[str,str]]]:
    if not re.search(r"^\(export\s+\(version\s+D\)",text):
        raise ValueError("expected legacy KiCad (export version D) netlist")
    # Names like "Net-(D15-Pad2)" contain parentheses *inside* quoted
    # strings. Do not split on raw punctuation inside those names.
    parsed={}
    chunks=re.split(r"(?m)^    \(net \(code ",text)[1:]
    if not chunks or len(chunks)>5000:
        raise ValueError("netlist missing bounded source nets")
    for chunk in chunks:
        match=re.match(r'(\d+)\) \(name ("(?:[^"\\]|\\.)*"|[^)]+)\)',chunk)
        if not match:
            raise ValueError("unrecognized KiCad net-name encoding")
        key=match.group(2)
        name=json.loads(key) if key.startswith('"') else key
        if name in parsed:
            raise ValueError("source net name duplicated")
        pairs=re.findall(r'\(node \(ref ([^)]*)\) \(pin ([^)]*)\)\)',chunk)
        if not pairs or len(set(pairs))!=len(pairs):
            raise ValueError("source contains missing or duplicated node")
        parsed[name]=sorted(pairs)
    return parsed


def _legacy_key_symbol(ref: str) -> str:
    if re.fullmatch(r"K[0-4][0-9A-D]",ref):
        return ref
    row_zero=re.fullmatch(r"K\[0\]([0-9])",ref)
    if row_zero:
        return "K0"+row_zero.group(1)
    alpha_column=re.fullmatch(r"K\[([A-D])\]([0-4])",ref)
    if alpha_column:
        return "K"+alpha_column.group(2)+alpha_column.group(1)
    raise ValueError("key does not match f.60 matrix macro index: "+ref)


def _extract_matrix_firmware(config_h: str, matrix_c: str,
                             keymap_h: str, keymap_c: str) -> dict:
    dims={}
    for name in ("ROWS","COLS"):
        match=re.search(rf"(?m)^#define\s+MATRIX_{name}\s+(\d+)\b",config_h)
        if not match:
            raise ValueError("missing firmware matrix dimension")
        dims[name.lower()]=int(match.group(1))
    start=matrix_c.find("static matrix_row_t read_cols(void)\n{")
    if start<0:
        raise ValueError("unsupported firmware read_cols source structure")
    end=matrix_c.find("\n}",start)
    reader=matrix_c[start:end]
    cols={}
    for port,bit,index in re.findall(
        r'PIN([BCDF])\s*&\s*\(1<<\s*(\d+)\)\s*\?\s*0\s*:\s*\(1<<\s*(\d+)\)',
        reader
    ):
        slot=int(index)
        if slot in cols:
            raise ValueError("firmware read_cols duplicates sensor index")
        cols[slot]=port+bit
    start=matrix_c.find("static void select_row(uint8_t row)\n{")
    if start<0:raise ValueError("unsupported firmware select_row implementation")
    end=matrix_c.find("\n}",start)
    selector=matrix_c[start:end]
    rows={}
    for slot,ddr,bit,port,bit2 in re.findall(
        r"case\s+(\d+)\s*:\s*DDR([BCDF])\s*\|=\s*\(1<<\s*(\d+)\)\s*;"
        r"\s*PORT([BCDF])\s*&=\s*~\(1<<\s*(\d+)\)",
        selector,
    ):
        if ddr!=port or bit!=bit2:
            raise ValueError("row direction and sink port disagree")
        if int(slot) in rows:
            raise ValueError("row selection duplicates index")
        rows[int(slot)]=ddr+bit
    if len(cols)!=dims["cols"] or set(cols)!=set(range(dims["cols"])):
        raise ValueError("firmware column GPIO count differs from config")
    if len(rows)!=dims["rows"] or set(rows)!=set(range(dims["rows"])):
        raise ValueError("firmware row GPIO count differs from config")

    macro=re.search(r"#define\s+KEYMAP\s*\((.*?)\)\s*\{",keymap_h,re.S)
    if not macro:
        raise ValueError("cannot find firmware layout indexing macro")
    defs=re.findall(r"\bK[0-4][0-9A-D]\b",macro.group(1))
    if len(defs)!=len(set(defs)):
        raise ValueError("keymap macro uses duplicate matrix indexes")
    if len(defs)>dims["cols"]*dims["rows"]:
        raise ValueError("keymap macro exceeds matrix dimensions")
    if not re.search(r"keymaps\s*\[\s*\]\s*\[\s*MATRIX_ROWS\s*\]\s*\[\s*MATRIX_COLS\s*\]",keymap_c):
        raise ValueError("firmware keymap dimensions do not follow expected matrix")
    layers=re.findall(r"\bKEYMAP\s*\(([^)]*)\)",keymap_c,re.S)
    actual_layers=[]
    for text in layers:
        symbols=[c.strip() for c in text.split(",")]
        if len(symbols)!=len(defs) or any(not sym or not re.fullmatch(r"[A-Z0-9_]+",sym) for sym in symbols):
            raise ValueError("firmware keymap layer does not enumerate every expected source key position")
        actual_layers.append(symbols)
    if len(actual_layers)<1:
        raise ValueError("firmware has no supported keymap layer")
    return {
        "matrix_rows":dims["rows"],
        "matrix_columns":dims["cols"],
        "firmware_column_gpio":[cols[k] for k in range(dims["cols"])],
        "firmware_row_gpio":[rows[k] for k in range(dims["rows"])],
        "occupied_keymap_positions":sorted(defs),
        "keymap_layers":len(actual_layers),
        "default_layer_keycodes":dict(zip(defs,actual_layers[0])),
    }


def audit_independent_source(
    board: dict,
    netlist_bytes: bytes,
    config_bytes: bytes,
    matrix_bytes: bytes,
    keymap_common_bytes: bytes,
    keymap_bytes: bytes,
    *,
    expected_hashes: dict[str,str] | None=None,
) -> dict:
    original=board.get("source_sha256")
    if not isinstance(original,str) or len(original)!=64:
        raise ValueError("unknown source PCB identity")
    raw={
        "keyboard.net":netlist_bytes,
        "config.h":config_bytes,
        "matrix.c":matrix_bytes,
        "keymap_common.h":keymap_common_bytes,
        "keymap.c":keymap_bytes,
    }
    hashes={name:_digest(data) for name,data in raw.items()}
    if expected_hashes and any(hashes.get(k)!=v for k,v in expected_hashes.items()):
        raise ValueError("independent upstream source file sha256 mismatch")
    netlist=legacy_netlist_nodes(netlist_bytes.decode("utf-8-sig"))
    pcb=defaultdict(set)
    for pad in board.get("pads",[]):
        name=str(pad.get("net",""))
        ref=str(pad.get("ref",""))
        number=str(pad.get("pad",""))
        if name and ref and number:
            pcb[name].add((ref,number))
    if not pcb:
        raise ValueError("PCB has no named source pad assignments")
    no_connect={}
    source_live={}
    for net,nodes in netlist.items():
        actual=set(nodes)
        skip=re.fullmatch(r"Net-\(U1-Pad(\d+)\)",net)
        if skip and actual=={("U1",skip.group(1))} and net not in pcb:
            no_connect[net]=sorted(actual)
        else:
            source_live[net]=actual
    schematic_only={
        net:sorted(source_live[net]-pcb.get(net,set()))
        for net in source_live if source_live[net]-pcb.get(net,set())
    }
    pcb_only={
        net:sorted(pcb[net]-source_live.get(net,set()))
        for net in pcb if pcb[net]-source_live.get(net,set())
    }
    if schematic_only or pcb_only:
        raise ValueError(
            f"independent schematic and PCB net assignments disagree: "
            f"schematic_only={list(schematic_only)[:7]} "
            f"pcb_only={list(pcb_only)[:7]}"
        )
    firmware=_extract_matrix_firmware(
        config_bytes.decode(),matrix_bytes.decode(),keymap_common_bytes.decode(),
        keymap_bytes.decode(),
    )
    original_keys=[str(sw["ref"]) for sw in board.get("switch_positions",[])]
    actual_symbols={_legacy_key_symbol(ref) for ref in original_keys}
    macro_symbols=set(firmware["occupied_keymap_positions"])
    if len(actual_symbols)!=len(original_keys) or actual_symbols!=macro_symbols:
        raise ValueError("firmware matrix occupied keys differ from PCB switch positions")
    controller_rows={f"/R{k}" for k in range(firmware["matrix_rows"])}
    controller_cols={f"/C{k}" for k in range(firmware["matrix_columns"])}
    pads_by_ref=defaultdict(dict)
    for pad in board["pads"]:
        if pad.get("net") and pad.get("pad"):
            pads_by_ref[str(pad["ref"])][str(pad["pad"])]=str(pad["net"])
    cpu=[x for x in board["footprints"] if "Teensy" in str(x.get("footprint",""))]
    if len(cpu)!=1:
        raise ValueError("source PCB does not identify its reference Teensy controller")
    source_cpu=pads_by_ref[cpu[0]["ref"]]
    if not controller_rows.issubset(source_cpu.values()) or not controller_cols.issubset(source_cpu.values()):
        raise ValueError("original PCB controller does not expose firmware matrix net names")
    if len(controller_rows|controller_cols)!=19:
        raise ValueError("firmware row/column net count differs")
    # Three-way check: the *independent* firmware KEYMAP macro position must
    # agree with the original PCB switch column and its diode-to-row net.
    from_diode=defaultdict(list)
    for ref,connections in pads_by_ref.items():
        if ref.startswith("D") and connections.get("1") in controller_rows and connections.get("2"):
            from_diode[connections["2"]].append((ref,connections["1"]))
    location_to_keycode={}
    for raw_ref in original_keys:
        expected=_legacy_key_symbol(raw_ref)
        key_pads=pads_by_ref.get(raw_ref,{})
        diode_candidates=from_diode.get(key_pads.get("1"),[])
        if len(diode_candidates)!=1 or key_pads.get("2") not in controller_cols:
            raise ValueError(f"original switch has no unique source diode-to-controller path: {raw_ref}")
        row_index=int(diode_candidates[0][1][2:])
        col_index=int(key_pads["2"][2:])
        observed=f"K{row_index}{col_index:X}"
        if observed!=expected:
            raise ValueError(f"firmware layout vs original PCB diode address mismatch at {raw_ref}: {observed}!={expected}")
        location_to_keycode[raw_ref]=firmware["default_layer_keycodes"][expected]
    total=sum(len(x) for x in source_live.values())
    if total!=sum(len(p) for p in pcb.values()):
        raise ValueError("source PCB and schematic total pad endpoint counts differ")
    result={
        "schema":"hs.keyboard-independent-source-schematic-firmware-audit.v1",
        "original_pcb_sha256":original,
        "source_hashes":hashes,
        "independent_schematic_net_count":len(netlist),
        "source_nets_in_original_pcb":len(source_live),
        "schematic_node_count":sum(len(v) for v in netlist.values()),
        "matched_original_pcb_net_nodes":total,
        "schematic_single_pin_no_connect_nodes":len(no_connect),
        "schematic_only_connected_pad_disagreements":0,
        "pcb_only_connected_pad_disagreements":0,
        "firmware_matrix_rows":firmware["matrix_rows"],
        "firmware_matrix_columns":firmware["matrix_columns"],
        "firmware_gpio_rows":firmware["firmware_row_gpio"],
        "firmware_gpio_columns":firmware["firmware_column_gpio"],
        "pcb_firmware_key_index_matches":len(actual_symbols),
        "firmware_keymap_slots":len(macro_symbols),
        "firmware_keymap_layers":firmware["keymap_layers"],
        "firmware_keymap_all_source_positions_present":True,
        "original_switch_to_firmware_default_keycode":dict(sorted(location_to_keycode.items())),
        "pcb_switch_diode_firmware_position_verified":len(location_to_keycode),
        "original_schematic_pinmap_verification":"PCB pad IDs equal schematic exported node IDs",
        "firmware_to_controller_physical_GPIO_mapping_proven":False,
        "firmware_compiled_or_flashed":False,
        "source_kicad_DRC_completed":False,
        "physical_donor_verified":False,
        "net_assignment_equivalence":True,
        "status":"PASS_SCH_TO_PCB_AND_FIRMWARE_INDEXING_UNPOWERED",
    }
    encoded=json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(",",":"))
    result["payload_sha256"]=_digest(encoded.encode())
    return result
