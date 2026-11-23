"""Legacy KiCad schematic and firmware parsing must fail closed on corruption."""
from __future__ import annotations

import pytest

from hardware_splicer.keyboard_splice_source_audit import (
    legacy_netlist_nodes, _legacy_key_symbol, _extract_matrix_firmware
)


def fixture_netlist():
    return '''(export (version D)
  (components
    (comp (ref K10)))
  (nets
    (net (code 1) (name "Net-(D10-Pad2)")
      (node (ref K10) (pin 1))
      (node (ref D10) (pin 2)))
    (net (code 2) (name /R1)
      (node (ref U1) (pin 4))
      (node (ref D10) (pin 1)))
    (net (code 3) (name /C0)
      (node (ref K10) (pin 2))
      (node (ref U1) (pin 27)))))
'''


def test_legacy_kicad_netlist_parser_preserves_parentheses_in_quoted_net_names():
    data=legacy_netlist_nodes(fixture_netlist().replace("\n","\r\n"))
    assert len(data)==3
    assert data["Net-(D10-Pad2)"]==[("D10","2"),("K10","1")]
    assert data["/R1"]==[("D10","1"),("U1","4")]
    assert data["/C0"]==[("K10","2"),("U1","27")]


@pytest.mark.parametrize("mutate",[
    lambda x: x.replace("(export (version D)","(export (version E)"),
    lambda x: x.replace("(node (ref K10) (pin 1))","(node (ref K10) (pin 1))\n      (node (ref K10) (pin 1))"),
    lambda x: x.replace("(name /R1)","(name /C0)"),
    lambda x: x.replace(' (name "Net-(D10-Pad2)")',' (name )'),
])
def test_legacy_netlist_rejects_malformed_or_duplicated_source(mutate):
    with pytest.raises(ValueError):
        legacy_netlist_nodes(mutate(fixture_netlist()))


def test_f60_reference_symbols_preserve_unusual_bracketed_names():
    assert _legacy_key_symbol("K[0]5")=="K05"
    assert _legacy_key_symbol("K[0]9")=="K09"
    assert _legacy_key_symbol("K[A]4")=="K4A"
    assert _legacy_key_symbol("K[D]2")=="K2D"
    assert _legacy_key_symbol("K15")=="K15"
    with pytest.raises(ValueError):
        _legacy_key_symbol("K[Q]3")


def simple_firmware():
    config="#define MATRIX_ROWS 2\n#define MATRIX_COLS 2\n"
    matrix='''static matrix_row_t read_cols(void)
{
  return (PINB&(1<<1) ? 0 : (1<<0)) |
         (PINF&(1<<4) ? 0 : (1<<1));
}
static void select_row(uint8_t row)
{
    switch (row) {
        case 0:
            DDRD |= (1<<0);
            PORTD &= ~(1<<0);
            break;
        case 1:
            DDRB |= (1<<2);
            PORTB &= ~(1<<2);
            break;
    }
}
'''
    common="#define KEYMAP(K00, K01, K10, K11) { K00, K01, K10, K11 }\n"
    keymap='''const uint8_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
        [0] = KEYMAP(ESC, Q, A, Z),
        [1] = KEYMAP(GRV, F1, F2, F3),
    };
'''
    return config,matrix,common,keymap


def test_firmware_reader_derives_gpio_directly_from_matrix_implementation():
    data=_extract_matrix_firmware(*simple_firmware())
    assert data["matrix_rows"]==2
    assert data["matrix_columns"]==2
    assert data["firmware_column_gpio"]==["B1","F4"]
    assert data["firmware_row_gpio"]==["D0","B2"]
    assert data["keymap_layers"]==2
    assert data["default_layer_keycodes"]=={
        "K00":"ESC","K01":"Q","K10":"A","K11":"Z"
    }


@pytest.mark.parametrize("change",[
    "matrix_dimension","duplicate_column","wrong_row_low_port","wrong_keymap_size"
])
def test_firmware_source_mismatch_is_not_silently_accepted(change):
    config,matrix,common,keymap=simple_firmware()
    if change=="matrix_dimension":
        config=config.replace("MATRIX_ROWS 2","MATRIX_ROWS 3")
    elif change=="duplicate_column":
        matrix=matrix.replace("(1<<1));","(1<<0));")
    elif change=="wrong_row_low_port":
        matrix=matrix.replace("PORTD &= ~(1<<0);","PORTB &= ~(1<<0);")
    else:
        keymap=keymap.replace("ESC, Q, A, Z","ESC, Q, A")
    with pytest.raises(ValueError):
        _extract_matrix_firmware(config,matrix,common,keymap)
