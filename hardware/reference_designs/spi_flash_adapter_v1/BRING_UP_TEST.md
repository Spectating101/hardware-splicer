# First-article bring-up: SPI flash adapter v1

Procedure dated **2026-11-15**, board revision **0.2-modeled**. **Not yet executed.**
Target: the populated **W25Q128JWSIQ**, a 1.8 V SOIC-8 208-mil flash, with expected
JEDEC ID **EF 60 18**. This test establishes one board's supply and read-ID behavior;
it does not qualify write/erase, endurance, timing margins or production reliability.
Retain the design's independent EE review and bench authorization prerequisites.

## Equipment and preparation

Use a DMM, current-limited adjustable supply, fine probes, magnification, removable
2.54 mm shunt, and preferably an oscilloscope with short ground springs. Use a
**3.3 V I/O FT232H USB-SPI breakout** as the inexpensive programmer (for example
[Adafruit 2264, $14.95 observed 2026-11-15](https://www.adafruit.com/product/2264)).
FT232H is used only to send read-ID here. Confirm its VCCIO is 3.3 V; verify idle
signal levels with a meter/scope before connection. A 3.3 V power pin alone does
not prove 3.3 V I/O. Do not use a 5 V-output CH341A variant or wire a programmer
directly to the 1.8 V DUT pins. Connect only through J1.

Photograph both sides and U1/U2/U3 markings; assign a nonpersonal board ID such as
`spi-v02-01`. Record `fab/manifest.json`, PCB/ZIP hashes, date, instruments and meter
lead resistance in a **private** bench log. Confirm U2 is JW, not JV; all pin-1
marks match the PCB pad 1; C2 is installed; no solder bridges; R1/R4 absent; JP1 open.
All tests below are stop-on-failure. Remove power before rework or fitting links.

## Cold checks: USB and supply disconnected

The following resistance limits are conservative screening thresholds, not simulated
or measured characteristics. Allow capacitors to charge from the DMM for 10 seconds;
reverse leads if a semiconductor junction affects the result. An unexpectedly low
reading is a stop for diagnosis, even if caused by a legitimate conduction path.

| Check | Pass / stop value |
| --- | --- |
| J1.2 to TP4/TP17/TP18 and U2.4 | <1 Ω after subtracting lead resistance |
| TP2 to U1.1, U3.1 and U3.3 | <1 Ω |
| TP3 to U3.5; TP15 to U1.14 and U2.8 | <1 Ω within each net |
| TP2/TP3/TP15 to GND | Settled >1 kΩ, no persistent continuity tone; <1 kΩ stops |
| R1 pads 1–2; R4 pads 1–2 | >100 kΩ with links absent; low reading stops |
| JP1 open, TP16 to GND through R7 | 9–11 kΩ; OE must not be shorted to DUT_1V8 |
| R5: J1.5/TP9 to J1.1/TP1 | 9–11 kΩ |
| R6: U2.1/TP10 to TP15; R2: U2.3/TP13 to TP15; R3: U2.7/TP14 to TP15 | 9–11 kΩ each |
| Host pins J1.3/.4/.5/.6 to U1.2/.3/.4/.5 respectively | <1 Ω each; no adjacent solder shorts |
| U1.13/.12/.11/.10 to U2.6/.5/.1/.2 respectively | <1 Ω each; no adjacent solder shorts |

Do not expect continuity *through* the translator from host to DUT: those are
active level-shifted paths. Test pads map as follows:

| Pads | Nets |
| --- | --- |
| TP1 / TP2 / TP3 / TP15 | HOST_3V3 / 3V3 / regulator 1V8 / DUT_1V8 |
| TP5 / TP6 | Host / DUT SCLK |
| TP7 / TP8 | Host / DUT MOSI |
| TP9 / TP10 | Host / DUT CS# |
| TP11 / TP12 | Host / DUT MISO |
| TP13 / TP14 / TP16 | DUT IO2 / DUT IO3 / translator OE |
| TP4 / TP17 / TP18 | GND |

## Supply acceptance before enabling SPI

1. Keep **R1, R4 and JP1 open**, J1 disconnected. Connect supply negative to TP4
   first; positive to **TP2 / R1 pad 2**, never J1.1. Set 3.30 V, **10 mA limit**.
   Turn on. Pass: TP2 **3.20–3.40 V**, TP3 **1.75–1.85 V**, TP16 **<0.20 V**,
   no current-limit indication. TP15 must remain **<0.20 V** while isolated.
   Record settled current; stop if it reaches 10 mA or any part heats.
2. Power off, verify all rails <0.20 V, then fit **R4 only**, using the loose 0 Ω
   0603 resistor. Confirm R4 <1 Ω. Keep R1 absent for the entire externally powered
   test. Repeat at **50 mA limit**. Pass: TP2 **3.20–3.40 V**, TP3 and TP15
   **1.75–1.85 V**, TP16 **<0.20 V**, TP10/TP13/TP14 **1.60–1.85 V**; settled
   current **<50 mA** and no limit activation. These current ceilings are fault
   screens, not guaranteed nominal consumption.
3. Scope TP15 at startup with nearby TP18 ground. Flash VCC must settle inside
   **1.70–1.95 V** and never overshoot 1.95 V. Record the ramp and decay. A DMM-only
   pass is provisional because it cannot see overshoot. Let the rail stay above
   1.70 V at least **20 µs** before any CS assertion; waiting a full second here
   comfortably exceeds this minimum.

## USB-SPI wiring and read-only test

Install PyFtdi on a Linux bench machine in a local virtualenv (Python 3.10+):

```sh
python3 -m venv out/bench/venv
out/bench/venv/bin/pip install pyftdi==0.57.1
```

Install the distribution's libusb runtime and grant local USB access using the
[PyFtdi installation instructions](https://eblot.github.io/pyftdi/installation.html).
The FT232H pins below follow the [PyFtdi SPI pinout](https://eblot.github.io/pyftdi/pinout.html).
Keep wires under 10 cm. Leave the board powered by the bench supply and JP1 open.
Power the FT232H by USB first, then connect ground followed by signal wires:

| FT232H breakout pin | J1 pin / board net |
| --- | --- |
| GND | 2, GND |
| 3V / 3.3 V | 1, HOST_3V3, supplies only R5 because R1 stays absent |
| D0 / ADBUS0 | 3, HOST_SCLK |
| D1 / ADBUS1 | 4, HOST_MOSI |
| D3 / ADBUS3 (CS0) | 5, HOST_CS_N |
| D2 / ADBUS2 | 6, HOST_MISO |

Never connect the breakout's 5 V pin. Do not parallel its 3.3 V regulator with the
bench supply by fitting R1. Do not attach an unpowered programmer to driven pins.

Use the repository's existing bounded utility from the repository root. First
create a dry-run plan (no USB access):

```sh
out/bench/venv/bin/python scripts/run_spi_read_only_jedec_id.py \
  --frequency-hz 1000000 --trials 10 --output out/bench/plan.json
```

For an authorized physical run, bind the packaged campaign and use a nonpersonal
operator alias. `build_remote_fct_campaign.py` creates the revision-bound campaign
used by the existing bench workflow; run it with system Python for pcbnew:

```sh
/usr/bin/python3 hardware/reference_designs/spi_flash_adapter_v1/build_remote_fct_campaign.py \
  --output out/spi-flash-adapter-v1-remote-fct.zip
campaign_hash=$(sha256sum out/spi-flash-adapter-v1-remote-fct.zip | cut -d ' ' -f 1)
out/bench/venv/bin/python scripts/run_spi_read_only_jedec_id.py \
  --transport pyftdi --ftdi-url 'ftdi://ftdi:232h/1' \
  --frequency-hz 1000000 --trials 10 \
  --campaign-sha256 "sha256:$campaign_hash" \
  --test-article-id spi-v02-01 --operator-id bench-operator-01 \
  --operator-confirm-bench-authorized --execute --output out/bench/jedec-1mhz.jsonl
```

The generic FTDI URL assumes exactly one connected FT232H. Do not commit a serial
number-specific URL. The utility configures **mode 0**, SCLK/MOSI low and CS high,
then pauses *before sending any transfer*. While paused, measure TP9 **3.0–3.4 V**,
TP10 **1.6–1.85 V** and TP16 **<0.20 V**. Once the rail checks above pass, bridge
JP1 deliberately. Pass: OE/TP16 **1.6–1.85 V**, both CS nets remain high. Type
`ENABLED` at the prompt only then.

Each trial keeps CS low for **32 clocks**, transmitting **9F 00 00 00**, MSB first;
the first received byte is ignored, and the last three must be **EF 60 18**. This
uses [PyFtdi full-duplex exchange](https://eblot.github.io/pyftdi/api/spi.html) and
the W25Q128JW Read JEDEC ID instruction, section 8.2.27 of the
[manufacturer's Rev G datasheet](https://www.winbond.com/resource-files/W25Q128JW_RevG_07292021%20Plus.pdf).
No write-enable, program, erase, reset or status-write is sent.

Pass at 1 MHz requires **10/10 exact EF6018 responses**, utility exit code 0, no
current limit, rails still in range and no anomalous heating. `FFFFFF`, `000000`,
`EF4018` (a different flash family), inconsistent IDs, short reads or USB errors
are **failures**. With CS high, open JP1 before restarting the utility. If 1 MHz
passes, repeat the command with `--frequency-hz 5000000` and a new output filename
`out/bench/jedec-5mhz.jsonl`, leaving JP1 open until its prompt and repeating the
enable checks. Accept 5 MHz only on **10/10** correct responses and acceptable
waveforms. A 1 MHz-only pass is useful limited evidence, not a 5 MHz pass.

Capture TP5/6, TP7/8, TP9/10 and TP11/12 where possible. Check DUT pins remain
within **-0.3 V to DUT VCC + 0.4 V** and the host pins within their component
ratings, with no ringing crossing those limits. Hold powered for 60 seconds;
stop if any IC rises more than **10 °C above ambient**, rails leave limits, or
current reaches 50 mA. Record current/temperature before and after the dwell.

With CS high, **remove JP1 before power-down**, disconnect host signals, turn off
the supply, then USB. Verify TP15 falls below **0.8 V for at least 100 µs** before
another startup; verify <0.20 V before rework. Never back-power DUT_1V8 directly.
On failure, stop, save readings/captures and diagnose with power removed. Do not
raise current limits or try erase/program commands to make an ID failure disappear.

Keep the result as **NOT RUN** until real bench data exists. A completed private
record should include every cold/supply reading, measured SPI frequency and voltage,
both JSONL runs, photos, scope data and their hashes, exact rework/part markings,
and a separate PASS/FAIL at 1 MHz and 5 MHz. CAD verification and a dry run are
never substitutes for these measurements.
