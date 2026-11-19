# Shop fixture interface trials

Six trials test fit, registration and repeatability for existing shop workflows. The engineering reports identify the actual SPI adapter source, assumed stock and interfaces, and remaining physical acceptance.

| Product | Condition tested |
| --- | --- |
| [P022 shelf-pin jig](P022/README.md) | Indexing preserves the hole pitch across consecutive jig placements |
| [P024 PCB vise](P024/README.md) | Jaws grip the edges while underside parts clear the bed |
| [P033 18-contact fixture](P033/README.md) | Source test pads, keyed cassette, probe stroke and simulated named-lead continuity |
| [P034 staging carrier](P034/README.md) | Transfer hole positions, fiducial geometry, and nozzle clearance at the clamps |
| [P048 stencil registration](P048/README.md) | Aperture alignment across tolerance corners and clearance during lift |
| [P216 manual robot coupling](P216/README.md) | Latch engagement, register keying and tool-tip bound from seat fit |

Use Python 3.10 or later.

```bash
cd projects/engineering-opportunity-portfolio/catalog/engineering/fixture-wave
python3 verify.py
```

[Editable dimensions](designs.json) define the prototype assemblies and each negative control. The verifier reads the saved SVG geometry and, for P033, the contact CSV, requires each candidate to pass and each control to fail its expected criterion, and rebuilds exports in a temporary directory to detect stale files. [Saved measurements](results.json) include the nominal and rejected results for all six products.
