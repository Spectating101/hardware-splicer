# P033 18-contact programming and test fixture

18-probe SPI adapter cassette, asymmetric reverse-load tab, and 54 simulated continuity and travel cases.

[Candidate SVG](trial.svg) · [Rejected SVG](rejected.svg) · [Contact trace](trial.csv) · [Rejected trace](rejected.csv) · [Editable dimensions](../designs.json) · [Replay results](../results.json)

## Setup

This layout uses the repository SPI adapter source, with pad coordinates, board fingerprint and nets reproduced in the source record. Fit the correct orientation once when fastening the adapter in its cassette, then use the asymmetric external tab to block a reversed cassette. Set the hard stop from the measured probe working stroke. The shown trial assumptions reserve 0.10 mm radial tip margin and 0.18 mm stroke. Source names are passed through to the lead matrix. The matrix exercises simulated connection and stroke corners using an ideal conductor per named lead. The source path in the Hardware-Splicer repository is `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb`. [Source-board layout and fingerprint](../source-board.json)

## Negative control

Opening the TP12 lead reduces the connected rows to 17 probes and 15 distinct nets. The acceptance thresholds require all 18 physical access points and all 16 distinct nets.

## Physical acceptance

Perform the first test unpowered. Known ground points should be joined; unrelated nets must pass the intended isolation test. Verify expected probe motion and run a contact test after each of ten reloads. Record lead resistance and intermittent faults separately from geometry.

The catalog models a 25-sale result of NT$ -690.00 at its proposed price. Use the fixture trial and physical acceptance costs to decide whether reuse is economical for the actual job.
