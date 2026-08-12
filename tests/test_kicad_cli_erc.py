from hardware_splicer.pcb.kicad_cli_erc import _extract_violations


def test_extract_violations_preserves_kicad_9_root_shape() -> None:
    payload = {
        "kicad_version": "9.0.2",
        "violations": [
            {"severity": "error", "type": "pin_to_pin", "description": "conflict"},
            {"severity": "warning", "type": "lib_symbol_issues", "description": "library"},
        ],
    }

    assert _extract_violations(payload) == payload["violations"]


def test_extract_violations_flattens_kicad_10_sheet_shape_with_provenance() -> None:
    payload = {
        "kicad_version": "10.0.5",
        "sheets": [
            {
                "path": "/",
                "violations": [
                    {"severity": "error", "type": "power_pin_not_driven", "description": "root"}
                ],
            },
            {
                "path": "/child",
                "violations": [
                    {"severity": "warning", "type": "pin_to_pin", "description": "child"}
                ],
            },
        ],
    }

    assert _extract_violations(payload) == [
        {
            "severity": "error",
            "type": "power_pin_not_driven",
            "description": "root",
            "sheet_path": "/",
        },
        {
            "severity": "warning",
            "type": "pin_to_pin",
            "description": "child",
            "sheet_path": "/child",
        },
    ]


def test_extract_violations_ignores_malformed_entries() -> None:
    payload = {
        "sheets": [
            None,
            {"path": "/", "violations": [None, "bad", {"severity": "warning"}]},
        ]
    }

    assert _extract_violations(payload) == [{"severity": "warning", "sheet_path": "/"}]
