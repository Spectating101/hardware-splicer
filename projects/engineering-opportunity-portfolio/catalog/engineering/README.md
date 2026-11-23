# Hardware Splicer digital engineering archive

Open the [engineering reader](trials.html) for the complete list in order of modeled 25-sale return. Each entry links to editable inputs, results and the physical test that could invalidate the design. The [build decisions](build-decisions.md) compare shop use, sale economics and alternatives for the tester, coffee divider, rain recorder, inspection rover, arm and underwater camera. The [270-offer coverage table](coverage.csv) includes the test proposed for every offer.

Some studies reimport 3D parts or decode rendered images. Others test a signal protocol, jig feature, dimensional envelope or tolerance coupon. Scope is specified per entry. A millimetre of optical margin, a correctly detected open wire and a reachable simulated pose each answer a different engineering question. Quantities, labor, yield, margins, sourcing and demand remain estimates until measured.

The November edition covers **153 of 270** offers across the original four studies and additional model groups. It includes all 53 positive 25-sale scenarios, all 26 additional offers within five percentage points of break-even, and all five with a modeled first internal build below a comparable purchase ask. The other 117 have a product brief, cost model, and proposed acceptance check. See the [successful replay receipt](verification.json) for the exact IDs and input fingerprints.

## Original four detailed studies

| Product | Modeled 25-sale ROI | What was built and exercised | What determines the next decision |
|---|---:|---|---|
| [Single-station switch tester · P028](P028/README.md) | 56.3% | Four holder profiles for two named Omron switches. The first keeper interfered. The revised profiles have 0.195 mm minimum modeled radial clearance. Contact evaluation classified 448 synthetic cycles across 14 conditions and a separate interrupted-run replay. | Best first lab pilot. Measure real actuator force, travel and fixture registration. The small holder has just 0.020 mm of retaining land above its proposed minimum. |
| [6×6 film carrier · P010](P010/README.md) | 43.4% | Five printable solids and five cutting contours for a freestanding carrier. Two guide widths reduced worst-case sideways reload movement from 1.30 to 0.80 mm. Six deliberately adverse cases exposed loading or optical failures. | Try sacrificial developed film. The accepted model leaves only 0.074 mm loading clearance at its tightest limit. Film curl, scratches and corner sharpness still determine whether it is sellable. |
| [App-specific tablet keyguard · P217](P217/README.md) | 38.4% | Two full-size overlays, a keyed bench locator, backing and an offline 12-button board for a bare ninth-generation iPad. A one-button app change made the original overlay miss the new boundary by 2.188 mm. Regenerating changed only the affected opening. | Best test of design reuse. Each revised target retains at least 1.419 mm modeled margin. Actual case fit and user access require a fitting trial. About 35 extra fitting minutes per order consume the estimated profit. |
| [Board-pallet gripper fingers and nest · P047](P047/README.md) | 31.7% | Three tooling solids checked against the existing HS pallet. End-tab pickup missed the 1 mm handoff limit at 6.29 mm. Supporting both rails near the center of mass brought the modeled bound to 0.91 mm. | Bench-test the centered layout. It requires 66.6 mm open inside width and controlled pad heights. Mounting it on the stock SO-101 requires a separately costed mechanism. |

## Replay and reproduce

The offline reader, CSVs, drawings and reports open without installing engineering tools. The excerpt pages preserve original report links and full-resolution source files. An ordinary browser find on the reader searches all published studies.

Run the engineering suite from this directory. It copies each study into an isolated temporary directory, regenerates outputs or inspects frozen releases, runs the included controls, and reconciles the verified product IDs with the coverage table.

```sh
python3 verify.py --cad-python /path/to/cadquery-2.8/bin/python --native-python /path/to/native-cad/bin/python
```

The main interpreter used here has Python 3.13, Shapely 2.1+, OpenCV with ArUco (4.10), NumPy and SciPy. The first CAD interpreter supplies CadQuery 2.8 for the gripper and teaching-tool STEP exports. The second supplies CadQuery 2.6.1, trimesh and NumPy for the two earlier HS design releases. The native interpreters can be the same if both sets of dependencies and the geometry checks work. Each group also includes its own verifier. Most groups require only Python's standard library. The robot optical image comparison may vary with the OpenCV build.

To recalculate the financial scenarios and rebuild both offline indexes from the product CSV and trial manifests, run `python3 ../rebuild.py` (requires markdown-it-py). The workbook and downloadable archive in this edition were reconciled against the same product records.

The [host resource log](run-resources.csv) sampled available memory, free swap, load and memory pressure over 28.2 minutes of engineering and archive work. Available RAM reached a low of 12.27 GiB. Host-wide free swap reached zero. The large verification and workbook jobs used process scopes with explicit memory limits and zero swap allowance.
