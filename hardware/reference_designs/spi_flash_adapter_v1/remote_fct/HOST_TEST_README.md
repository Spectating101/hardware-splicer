# Bounded host test software

This bundle contains source for one read-only SPI transaction. It is not firmware for the
MCU-less adapter and it does not control bench power or translator OE.

## Host connection

Use a 3.3 V-logic SPI host. J1 is ordered:

1. `HOST_3V3`
2. `GND`
3. `HOST_SCLK`
4. `HOST_MOSI`
5. `HOST_CS_N`
6. `HOST_MISO`

Connect common ground first. Keep R1 open so the host rail cannot parallel the bench supply.
Do not attach an unpowered host to a driven adapter. Map the host's SCLK, MOSI, active-low CS
and MISO pins to J1; provider-specific adapter pin names must be recorded separately.

## Dependencies

Python 3.12 or newer plus one transport:

- Linux spidev: install the platform's `spidev` Python package and identify bus/device; or
- FT232H: install `pyftdi` and identify the exact FTDI URL and chip-select.

Dry-run inspection opens no device:

```bash
PYTHONPATH=src python scripts/run_spi_read_only_jedec_id.py --output jedec-dry-run.json
```

Live execution requires the exact campaign ZIP SHA-256, article/operator identities and prior
BENCH_POWER authorization. The program configures the host while JP1 remains open, then pauses.
After the rail/CS checks pass, bridge JP1 and type `ENABLED`.

```bash
PYTHONPATH=src python scripts/run_spi_read_only_jedec_id.py \
  --execute \
  --transport spidev --spidev-bus 0 --spidev-device 0 \
  --frequency-hz 1000000 --trials 10 \
  --campaign-sha256 sha256:<64-hex-digest> \
  --test-article-id <board-serial> --operator-id <operator-id> \
  --operator-confirm-bench-authorized \
  --output raw/jedec-1mhz.jsonl
```

Never reuse an output filename: the utility refuses to overwrite evidence. Live output is
append-only JSON Lines, reserved before the transport opens and flushed after every attempted
transaction so a mismatch, short read or interruption does not erase earlier observations.
The utility fixes mode 0,
8-bit MSB-first, active-low CS and a single full-duplex `9F 00 00 00` exchange. The first RX
byte is discarded and the remaining bytes must equal `EF 60 18`. There is no opcode option or
automatic recovery. A matching bounded transaction is not campaign acceptance. Preserve
mismatches and transport errors as returned evidence.
