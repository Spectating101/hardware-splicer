# In-house spring-probe fixture

A technician places a revision-matched board component-side up. A guide positions an array of spring probes over its exposed test pads. The intended bench routes each probe to a labeled instrument connection. The operator can then take a series of measurements without hunting for each pad again. This digital prototype covers the two plates that determine placement.

![Top view of the board and fixture hole pattern](contact-map.png)

## What exists

The source specimen is HS's [90 × 50 mm SPI adapter](../../hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb). Its [existing test plan](../../hardware/reference_designs/spi_flash_adapter_v1/remote_fct/PROVIDER_TEST_PLAN.md) identifies a recurring need to reach both sides of the voltage translator. The board has 18 exposed circular test pads on 16 distinct nets. Three pads reach ground.

* [Board carrier](board-carrier.step) supports the board at four mounting holes. Two diagonal locating pins enter the PCB. Its symmetric hole arrangement still allows a 180° board-loading error. An orientation feature that clears the populated board is an open design item.
* [Probe guide](probe-guide.step) has 18 through-bores of nominal 0.9 mm diameter for evaluation against the proposed socket system. Three asymmetrically placed post holes locate the plates relative to each other. Both STEP files have their own bottom face at Z = 0.
* [Geometry record](geometry.json) binds the source board hash, contact names, coordinates and tolerance assumptions to the generated pattern. The builder reopens both STEP files and checks circles at each end of every probe bore, the post pattern and the carrier locators.

In a revision exercise we moved TP12 by 2 mm in a temporary KiCad copy. The original guide failed the revised pattern. In the regenerated STEP, only that bore moved, from (60, 12) to (62, 12) mm. The old and new carrier solids had zero volume difference in both directions within 1e-8 mm³. A future pad-layout change can therefore reuse the carrier when its mounting geometry is still valid.

Under an assumed 0.5 mm effective tip diameter and 0.40 mm total radial positioning error at each pad, a 1.5 mm pad has 0.10 mm radial margin. At 0.80 mm displacement the tip envelope overhangs by 0.30 mm. These are sensitivity cases. Actual drill accuracy, fixture play, pad-to-hole registration, plate rotation and probe lean require measurements. The next digital design work is selecting the mating socket, checking populated-component heights, adding an orientation key, sizing underside supports, and defining plate travel and a hard stop from working probe stroke. Eighteen probes at the seller's nominal 75 gram-force would exert approximately 13 N combined if all reach that force. This sets the scale of the board-support problem. Physical contact reliability, retention, signal quality, cycle life and operator time remain open. [Probe specification](https://www.100y.com.tw/product/115491)

## What to spend and when

| Way to perform the job | Published price or internal allowance | When it makes sense |
| --- | --- | --- |
| Hand-probe with an existing meter | Time the operator on the real board | First articles, fault investigations, mixed donor lots |
| Single-row clip | US$10.95 listed, manufacturer showed out of stock | Six adjacent pads on 2.54 mm pitch. The specimen's pads are scattered. [Adafruit](https://www.adafruit.com/product/5433) |
| Generic compression jig plus HS insert | US$114 listed for jig, adaptation and delivery extra | Obtain its mounting drawing and compare the work to fit the insert with making a frame. Mechanical compatibility is open. [Oukaning](https://www.oukaning.com/products/oukaning-universal-pcb-testing-jig-pcba-circuit-board-test-fixture-tools) |
| Fully custom development fixture | Starts at US$999 | Clamshell actuation, supplier engineering and roughly 1,000 cycles according to the vendor. Request a comparable configuration if these capabilities matter. [FixturFab](https://fixturfab.com/fixtures/dev) |
| HS first fixture, budget scenario | US$95 materials plus 6 hours × US$24 = US$239 | Test a stable revision often enough for the operator time saving to pay for the work. |

Within the US$95 scenario, allow $10 for probe stock, $20 for sockets, wiring and breakout, $25 for fabricated plates, $25 for posts, stop and clamp hardware, and $15 for scrap and small supplies. Twenty P50-B1 probes cover 18 positions and two spares. A Taiwanese seller lists ten for NT$99. A second seller lists US$0.19 per probe in multiples of ten. These are sourcing leads. The remaining amounts are targets pending quotes and the six hours are a design, assembly and review allowance. The scenario assumes access to ordinary bench instruments. Freight, tool acquisition, model usage, maintenance and retries increase the threshold. [Taiwan listing](https://www.100y.com.tw/product/115491) · [Digole listing](https://www.digole.com/index.php?productID=497)

At $24/hour, four minutes saved per board is $1.60. The $239 scenario breaks even on the 150th use. At two minutes it takes 299 uses. At eight minutes it takes 75. For a lot of 30, four minutes per board buys only $48 of work. The comparison should use repeated tests on the same usable pattern and include false contacts and reloads. Payback against a vendor purchase applies only when the company actually needs and would buy that capability. Salvaged frames or plates earn credit after dimensional inspection, adaptation time and expected scrap are costed.

## Reproduce

From the repo root, use the same CadQuery and Matplotlib environment as the [inspection nest](../pcb-inspection-nest/requirements.txt) and a system Python with KiCad's pcbnew bindings.

```sh
.cache/hardware-splicer/digital-native-venv/bin/python projects/bench-probe-fixture/build.py --output /tmp/hs-probe-fixture
.cache/hardware-splicer/digital-native-venv/bin/python projects/bench-probe-fixture/verify_revision.py
```

Use `--board` for a revised source and `--kicad-python` for the interpreter with pcbnew. The generator targets rectangular boards within the common plate envelope, with this four-hole mounting scheme and round front-side test pads. Review each new board's component clearance and registration before using the result.

## Source-revision electrical qualification (20 November 2026)

The historical trial that moved TP12 **+2 mm on X** only demonstrated
mechanical response: the original probe-guide bore moved and the carrier stayed
unchanged. The unchanged-copper source **failed native KiCad DRC**, and even
adding a straight trace on the original board path still conflicted with
another net. These are not electrically accepted PCB revisions.

The [external EDA pilot](../external-eda-pilot/README.md) found a different
**+1 mm X / −1 mm Y** move with a short F.Cu track that passes KiCad DRC
(0 violations, 0 unconnected pads), remains schematic-to-PCB equivalent under
akcli, and produces a matching probe guide at (61,13) mm instead of (60,12) mm.
Physical probe contact and fixture fabrication remain unverified.
