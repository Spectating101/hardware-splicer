# Manual shop fixture trials

Twelve independent digital bench trials cover bookbinding, leatherworking, instrument repair, woodworking, ceramics and textiles. Eight have a positive 25-sale result in the catalog's proposed-price model. Four explore geometry and buildability for educational or internal use. Refer to each product report for the modeled result and the physical acceptance test.

| Product | Design decision tested |
| --- | --- |
| [P232 signature cradle](P232/README.md) | Awl bore envelope remains over the slit between the cradle rails |
| [P233 nipping press](P233/README.md) | Screw access and thread engagement across the clamp opening range |
| [P234 sewing frame](P234/README.md) | Sliding anchors fit and support two actual cord layouts |
| [P235 spine finishing press](P235/README.md) | Full-length spine-tool clearance within a gripped book section |
| [P236 fan-gluing clamp](P236/README.md) | Tilt stroke clears the deck and seats against each end stop |
| [P240 rotary punch fence](P240/README.md) | Two-point fence restraint at three offsets on an assumed host |
| [P241 dye roller](P241/README.md) | Bath immersion, floor clearance and cleaning travel |
| [P246 thickness sander](P246/README.md) | Carrier clearance and abrasive contact across the blank |
| [P251 radius routing template](P251/README.md) | Guide-to-cut radius and clamping land on a narrow coupon |
| [P261 pottery dividing disc](P261/README.md) | Tick-angle accuracy and replaceable centering registration |
| [P263 fringe twister](P263/README.md) | Crank-link fit and transmission through a full revolution |
| [P264 warping board](P264/README.md) | Repeatable tangent paths and removable peg spacing |

Open each `trial.svg` for dimensioned, true-scale orthographic views. View coordinates are in millimetres. The assembly, component geometry and stock dimensions start from editable values in [designs.json](designs.json). Assumed hardware and host coupons need physical measurement. The drawings support prototype layout and include named geometry for extraction to CAM after selecting stock thickness, tool fit and tolerances for the intended process.

Use Python 3.10 or later to replay all 12 trials.

```bash
cd projects/engineering-opportunity-portfolio/catalog/engineering/shop-wave
python3 verify.py
```

The checker parses the saved candidate and rejected SVGs, measures named entities independently of the parameter file, checks the expected rejection, and rebuilds both revisions in a temporary directory to detect stale exports. [results.json](results.json) records all measurement checks. To iterate, edit the desired dimensions, run `python3 build.py`, inspect the changes, and use `python3 verify.py --write` to refresh the measurements. Each report specifies a bench test for the behaviors that depend on real material, hardware, loads or process.
