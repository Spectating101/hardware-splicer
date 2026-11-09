"""Generate ZMK source files from the *actual KiCad key coordinate receipt*.

This is firmware configuration, not a claim of a paired/working Bluetooth
device. Key order is ROW-MAJOR left then right for each of five scan rows.

Pin map (one XIAO nRF52840 per half): COL0..4 -> D0..D4, ROW0..4 -> D5..D9.
Diodes: PCB SW pin1 COL, SW pin2 -> 1N4148W anode, cathode -> ROW,
so "col2row" in ZMK.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CONF=HERE/"config"
SHIELD=CONF/"boards/shields/thor_split"

def _write(path:Path,contents:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(contents.strip()+"\n")


def generate():
    geom=json.loads((ROOT/"generated/fit_report.json").read_text())
    profile=geom["variants"]["detachable_9mm"]
    per={}
    for side in ("left","right"):
        path=ROOT/f"generated/detachable_9mm/{side}_25_key_locations.csv"
        with path.open() as f:rows=list(csv.DictReader(f))
        assert len(rows)==25
        ordered=sorted(rows,key=lambda d:(int(d["row"]),int(d["col"])))
        assert [r["label"] for r in ordered] == [k["label"] for k in profile["sides"][0 if side=="left" else 1]["keys"]]
        per[side]=ordered
    # Source of truth for electronic row/col and legends
    notes={
        "schema":"hs.thor.zmk_split_matrix.v1",
        "board":"seeeduino_xiao_ble",
        "board_revision_to_confirm":"Seeed Studio XIAO nRF52840, NOT ESP32 XIAO or RP2040",
        "original_design":"detachable_9mm/left & right 25-key native KiCad 9 boards",
        "matrix_each_half":[5,5],
        "gpio_columns":["D0","D1","D2","D3","D4"],
        "gpio_rows":["D5","D6","D7","D8","D9"],
        "row_gpio_pull":"down",
        "active_columns":"high",
        "diode_direction":"col2row",
        "diode_physical_path":"SW pad1 COL -> SW pad2 KEY -> diode pad2 anode -> diode pad1 cathode ROW",
        "mcus":2,
        "connection":"left central BLE HID to Android/Linux; right peripheral BLE to left",
        "no_battery_required_for_first_usb_powered_bench":True,
        "proof":{"KiCad_netlist_rows":True,"generated_ZMK_keymap":True,
                 "ZMK_compiled":False,"two_physical_mcu_booted":False,
                 "all_50_real_switches_scanned":False,"Bluetooth_host_paired":False,
                 "battery_charger_approved":False},
        "wiring_requires_external_testpad_harness_and_ESD_protection":True,
        "positions":{
            side:[{"row":int(k["row"]),"col":int(k["col"]),"label":k["label"],"id":k["id"]}
                  for k in rows] for side,rows in per.items()
        },
    }
    # Kconfig and module
    _write(SHIELD/"Kconfig.shield","""
config SHIELD_THOR_SPLIT_LEFT
    def_bool $(shields_list_contains,thor_split_left)

config SHIELD_THOR_SPLIT_RIGHT
    def_bool $(shields_list_contains,thor_split_right)
""")
    _write(SHIELD/"Kconfig.defconfig","""
if SHIELD_THOR_SPLIT_LEFT

config ZMK_KEYBOARD_NAME
    default "HS Thor Keys"

config ZMK_SPLIT_ROLE_CENTRAL
    default y

endif

if SHIELD_THOR_SPLIT_LEFT || SHIELD_THOR_SPLIT_RIGHT

config ZMK_SPLIT
    default y

endif
""")
    matrix_rows=[]
    for r in range(5):
        matrix_rows.append(" ".join(f"RC({r},{c})" for c in range(10)))
    rows_gpios=",\n".join(
        f"            <&xiao_d {i} (GPIO_ACTIVE_HIGH | GPIO_PULL_DOWN)>"
        for i in range(5,10))
    cols_gpios=",\n".join(
        f"            <&xiao_d {i} GPIO_ACTIVE_HIGH>"
        for i in range(5))
    _write(SHIELD/"thor_split.dtsi",f"""
#include <dt-bindings/zmk/matrix_transform.h>
#include <zephyr/dt-bindings/gpio/gpio.h>

/ {{
    kscan0: kscan0 {{
        compatible = "zmk,kscan-gpio-matrix";
        wakeup-source;
        diode-direction = "col2row";
        col-gpios =
{cols_gpios};
        row-gpios =
{rows_gpios};
    }};
    default_transform: keymap_transform_0 {{
        compatible = "zmk,matrix-transform";
        rows = <5>;
        columns = <10>;
        map = <
            {"\n            ".join(matrix_rows)}
        >;
    }};
    physical_layout0: physical_layout_0 {{
        compatible = "zmk,physical-layout";
        display-name = "HS Thor 5x5 each";
        kscan = <&kscan0>;
        transform = <&default_transform>;
    }};
    chosen {{
        zmk,physical-layout = &physical_layout0;
    }};
}};
""")
    _write(SHIELD/"thor_split_left.overlay",'#include "thor_split.dtsi"')
    _write(SHIELD/"thor_split_right.overlay",'''
#include "thor_split.dtsi"
&default_transform {
    col-offset = <5>;
};
''')
    # Must exactly match the interleaved transform, left 5 + right 5 each row.
    key_names={
        ";":"SEMI",",":"COMMA",".":"DOT","/":"FSLH",
        "SHIFT":"LSHFT","CTRL":"LCTRL","ALT":"LALT","TAB":"TAB",
        "SPACE":"SPACE","ENTER":"RET","BSPC":"BSPC","ESC":"ESC",
        "1":"N1","2":"N2","3":"N3","4":"N4","5":"N5",
        "6":"N6","7":"N7","8":"N8","9":"N9","0":"N0",
    }
    base=[]
    for r in range(5):
        s=[]
        for side in ("left","right"):
            for k in per[side][r*5:r*5+5]:
                label=k["label"]
                if label in ("FN","SYM"):s.append("&mo 1")
                else:s.append(f"&kp {key_names.get(label,label)}")
        assert len(s)==10
        base.append(s)
    # Programmer symbols + arrow navigation when holding FN or SYM.
    # In layer1, original FN and SYM are &trans (keep momentary role).
    codes=[
       ["GRAVE","EXCL","AT","HASH","DLLR", "PRCNT","CARET","AMPS","ASTRK","TILDE"],
       ["EQUAL","MINUS","PLUS","LBRC","RBRC", "LBKT","RBKT","BSLH","PIPE","SQT"],
       ["F1","F2","F3","F4","F5", "LEFT","DOWN","UP","RIGHT","DEL"],
       ["F6","F7","F8","F9","F10", "F11","F12","HOME","END","PG_UP"],
       ["LSHFT","LCTRL","LALT","TAB",None, None,"SPACE","RET","BSPC","ESC"],
    ]
    symbols=[[("&trans" if v is None else f"&kp {v}") for v in row] for row in codes]
    def keymap_rows(rows):
        return "\n".join("            "+" ".join(row) for row in rows)
    _write(SHIELD/"thor_split.keymap",f"""
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

#define BASE 0
#define CODE 1

/ {{
    keymap {{
        compatible = "zmk,keymap";
        default_layer {{
            display-name = "QWERTY";
            bindings = <
{keymap_rows(base)}
            >;
        }};
        code_layer {{
            display-name = "Code / Nav";
            bindings = <
{keymap_rows(symbols)}
            >;
        }};
    }};
}};
""")
    _write(SHIELD/"thor_split.zmk.yml","""
file_format: "1"
id: thor_split
name: HS Thor Split QWERTY
type: shield
requires: [xiao]
features: [keys]
siblings: [thor_split_left, thor_split_right]
""")
    _write(CONF/"west.yml","""
manifest:
  defaults:
    revision: v0.3
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
  projects:
    - name: zmk
      remote: zmkfirmware
      import: app/west.yml
  self:
    path: config
""")
    _write(HERE/"build.yaml","""
---
include:
  - board: seeeduino_xiao_ble
    shield: thor_split_left
    artifact-name: hs_thor_left
  - board: seeeduino_xiao_ble
    shield: thor_split_right
    artifact-name: hs_thor_right
""")
    (HERE/"matrix_wiring.json").write_text(json.dumps(notes,indent=2)+"\n")
    return notes

if __name__=="__main__":
    result=generate()
    print("50 mapped switch positions; "+str(len(result["positions"]["left"]))+" left + "+
          str(len(result["positions"]["right"]))+" right, compile not yet verified")
