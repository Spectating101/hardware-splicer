# HS Thor 50-key split QWERTY — ZMK firmware candidate

**Status:** Two independently compiled upstream ZMK v0.3 nRF52840 `.uf2` firmware artifacts were confirmed in [GitHub Actions run #42654086871](https://github.com/Spectating101/hardware-splicer/actions/runs/42654086871). Their sizes and SHA-256 hashes are retained in `firmware_build_receipt.json`. **No MCU was flashed, no physical keyboard was wired or paired, and no battery was installed.**

## Why this is an independent keyboard

A retained AYN Thor uses Android or experimental Linux. The first physically testable keyboard should be **two separate small 25-key modules** behaving as a single standard Bluetooth HID QWERTY keyboard. It must not require access to AYN gamepad ribbon connectors or modifications to the Thor's internal charging power circuit. We reuse [ZMK](https://zmk.dev/docs/features/split-keyboards), including its central/peripheral BLE split architecture.

The source of truth for row/column geometry is **PR #316's fully routed 9 mm external wing keyboard PCBs**; generator `make_config.py` derives config/wiring from those exact key CSV receipts, not a guessed layout.

## First LOW-risk USB-only electronics bench

- **Two** *genuine* Seeed XIAO **nRF52840** development boards, one per keyboard half. Do not substitute an ESP32 or RP2040 XIAO. This is a reference footprint/pin scheme, not a vendor-qualified end-product BOM.
- Each PCB has **10 unprotected solder test pads**, 5 × COL and 5 × ROW. An *external temporary insulated test harness* must connect these to **D0–D4 (COL0–4)** and **D5–D9 (ROW0–4)** on the corresponding XIAO. One row/column line MUST map to exactly one pad. Do not treat test pads as permanent connectors or connect the Thor's button ribbon.
- Each PCB routes **25 real KiCad-native KMR2 switch footprints**, 25 SOD-123 diodes, and a 5×5 matrix. Diode **pad 2 is anode** from the switch intermediate node, **pad 1 is cathode** toward ROW. ZMK `diode-direction = "col2row"` is deliberate and supported by actual KiCad matrix inspection.
- Power *each XIAO development board* initially from its own manufacturer-compliant **USB input** with proper cable and safe supply. **Do not connect or charge raw lithium cells, nor tap AYN Thor battery rails**. The right half speaks to the left via Bluetooth as a ZMK peripheral; the left central advertises a single HID keyboard.
- Never flash from an unreviewed build artifact. Confirm exact XIAO nRF hardware/bootloader, review the compiled image and physically identify solder points. There is no claim of physical firmware functionality from CI alone.

### Software layout (one row of five keys each side)

| Row | Left half | Right half |
| --- | --- | --- |
| 1 | Q W E R T | Y U I O P |
| 2 | A S D F G | H J K L ; |
| 3 | Z X C V B | N M , . / |
| 4 | 1 2 3 4 5 | 6 7 8 9 0 |
| 5 | Shift Ctrl Alt Tab Fn | Sym Space Enter Backspace Esc |

**Fn/Sym:** hold either to switch to a code/navigation layer with brackets/braces, pipe, backslash, punctuation, arrows, function keys and Home/End. Real simultaneous modifier-key operation, holding behavior and typing speed are **unverified on actual switches**.

## Code and reproducibility

- `build.yaml`: two `seeeduino_xiao_ble` targets, left central and right peripheral
- `config/boards/shields/thor_split`: ZMK Kconfig, overlay/physical layout, row/column GPIO, 50-key keymap
- `config/west.yml`: upstream ZMK manifest pinned to v0.3
- `matrix_wiring.json`: pin and geometry source authority; the generator itself does not compile firmware
- `firmware_build_receipt.json`: separate verified Zephyr build provenance, artifact sizes, Nordic nRF52840 UF2 signatures, and explicit unflashed/untested flags
- `make_config.py`: regenerates ZMK source directly from the 9 mm-wing keyboard CSVs.
- `.github/workflows/hs-thor-zmk-firmware.yml`: real ZMK/Zephyr builds, with build workspace rooted under this directory, not at the HS repo root.

To rerun source checks locally:

```bash
python3 examples/cyberdeck/thor_split_qwerty/zmk/make_config.py
PYTHONPATH=src python3 -m pytest -q tests/test_thor_zmk_matrix.py
```

On a proper ZMK west/toolchain setup (the GitHub Actions container is recommended):

```bash
cd examples/cyberdeck/thor_split_qwerty/zmk
west init -l config
west update --fetch-opt=--filter=tree:0
west zephyr-export
west build -s zmk/app -d build_left -b seeeduino_xiao_ble \
  -- -DZMK_CONFIG="$PWD/config" -DSHIELD=thor_split_left
west build -s zmk/app -d build_right -b seeeduino_xiao_ble \
  -- -DZMK_CONFIG="$PWD/config" -DSHIELD=thor_split_right
```

Once real compiled, a `zmk.uf2` is a **firmware image, not a functional test**. After flashing two confirmed development boards, validate 50 switch position events, layer mapping, ghosting, host Bluetooth pairing, sleep/wake, measured current and BLE reconnection. Then prototype a temporary enclosure and thumb typing on real key switches. Only after those gates may a physical Thor control-replacement assembly be justified.

**Current manufacturing and battery authority: NO.**
