"""A real upstream ZMK split-shield source config bound to actual KiCad netlist.

Source/key mapping truth only. *Never* call this a successful physical BLE
pairing/keyboard/charging trial. The upstream ZMK CI job compiles firmware.
"""
import csv,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
THOR=ROOT/"examples/cyberdeck/thor_split_qwerty"
Z=THOR/"zmk"
S=Z/"config/boards/shields/thor_split"
CONF=json.loads((Z/"matrix_wiring.json").read_text())

def _bindings(keymap,layer):
    x=re.search(rf"\b{layer}_layer\s*\{{.*?bindings\s*=\s*<(.*?)>;",
                keymap,re.S)
    assert x is not None,layer
    # ZMK '&kp key' vs '&mo 1', '&trans' are single behaviors.
    return re.findall(r"&kp\s+\w+|&mo\s+\d+|&trans",x.group(1))

def test_full_matrix_generated_from_real_per_key_KiCad_manifest():
    assert CONF["matrix_each_half"]==[5,5]
    assert CONF["gpio_columns"]==["D0","D1","D2","D3","D4"]
    assert CONF["gpio_rows"]==["D5","D6","D7","D8","D9"]
    assert CONF["diode_direction"]=="col2row"
    for side in ("left","right"):
        path=THOR/f"generated/detachable_9mm/{side}_25_key_locations.csv"
        with path.open() as f:
            actual=list(csv.DictReader(f))
        expected=CONF["positions"][side]
        assert len(actual)==len(expected)==25
        assert [(int(r["row"]),int(r["col"]),r["label"],r["id"]) for r in actual]==[
            (r["row"],r["col"],r["label"],r["id"]) for r in expected]
        assert len({(r["row"],r["col"]) for r in expected})==25

def test_zmk_split_and_exact_two_generated_halves():
    k=(S/"Kconfig.shield").read_text()
    defaults=(S/"Kconfig.defconfig").read_text()
    for half in ("left","right"):
        assert f"thor_split_{half}" in k
        assert (S/f"thor_split_{half}.overlay").exists()
    assert "ZMK_SPLIT_ROLE_CENTRAL" in defaults
    assert 'default "HS Thor Keys"' in defaults
    assert defaults.count("config ZMK_SPLIT\n")==1
    assert "col-offset = <5>;" in (S/"thor_split_right.overlay").read_text()
    assert "col-offset" not in (S/"thor_split_left.overlay").read_text()
    builds=(Z/"build.yaml").read_text()
    assert "board: seeeduino_xiao_ble" in builds
    assert "shield: thor_split_left" in builds
    assert "shield: thor_split_right" in builds

def test_kscan_pins_match_actual_test_pad_nets_and_polarity():
    s=(S/"thor_split.dtsi").read_text()
    assert 'compatible = "zmk,kscan-gpio-matrix";' in s
    assert 'diode-direction = "col2row";' in s
    assert s.count("GPIO_PULL_DOWN")==5
    assert [int(x) for x in re.findall(r"<&xiao_d\s+(\d+)",s)]==list(range(10))
    assert 'rows = <5>;' in s and 'columns = <10>;' in s
    assert "zmk,physical-layout = &physical_layout0;" in s
    assert "compatible = \"zmk,physical-layout\";" in s
    positions=[(int(a),int(b)) for a,b in re.findall(r"\bRC\((\d+),(\d+)\)",s)]
    assert positions==[(r,c) for r in range(5) for c in range(10)]

def test_true_qwerty_mapping_order_across_two_halves_and_programmer_layer():
    s=(S/"thor_split.keymap").read_text()
    a=_bindings(s,"default")
    b=_bindings(s,"code")
    assert len(a)==len(b)==50,(len(a),len(b))
    assert a[:10]==[f"&kp {k}" for k in list("QWERTYUIOP")]
    assert a[10:20]==[f"&kp {k}" for k in list("ASDFGHJKL")]+["&kp SEMI"]
    assert a[20:30]==[f"&kp {k}" for k in list("ZXCVBNM")]+["&kp COMMA","&kp DOT","&kp FSLH"]
    assert a[30:40]==[f"&kp N{x}" for x in [1,2,3,4,5,6,7,8,9,0]]
    assert a[44]=="&mo 1" and a[45]=="&mo 1"
    assert a[46:] == ["&kp SPACE","&kp RET","&kp BSPC","&kp ESC"]
    for binding in ("&kp LBRC","&kp RBRC","&kp LBKT","&kp RBKT","&kp BSLH",
                    "&kp PIPE","&kp GRAVE","&kp LEFT","&kp UP","&kp RIGHT"):
        assert binding in b
    assert b[44]=="&trans" and b[45]=="&trans"

def test_provenance_aware_no_physical_bluetooth_claims():
    assert CONF["board"]=="seeeduino_xiao_ble"
    assert CONF["no_battery_required_for_first_usb_powered_bench"] is True
    assert CONF["wiring_requires_external_testpad_harness_and_ESD_protection"]
    for key,value in CONF["proof"].items():
        if key in ("KiCad_netlist_rows","generated_ZMK_keymap"):
            assert value is True
        else:
            assert value is False,key
    assert "charger" not in (S/"thor_split.dtsi").read_text().lower()

def test_ZMK_manifest_and_build_inputs_are_upstream_but_no_unearned_image():
    west=(Z/"config/west.yml").read_text()
    assert "https://github.com/zmkfirmware" in west
    assert "revision: v0.3" in west
    workflow=(ROOT/".github/workflows/hs-thor-zmk-firmware.yml").read_text()
    assert "zmkfirmware/zmk/.github/workflows/build-user-config.yml@v0.3" in workflow
    assert "build_matrix_path: examples/cyberdeck/thor_split_qwerty/zmk/build.yaml" in workflow
    assert "config_path: examples/cyberdeck/thor_split_qwerty/zmk/config" in workflow
