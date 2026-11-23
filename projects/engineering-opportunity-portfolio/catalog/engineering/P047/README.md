# Gripper shoes and locating nest for the HS board pallet

The released design grips both long rails of the existing 114 × 58 × 6 mm HS SPI-adapter pallet. An 8 mm-high nest supports its perimeter and leaves the board opening and jaw sweeps clear. In the modeled vertical handoff, moving the pickup from the end tab to the two rails reduced the calculated edge error from **6.29 mm to at most 0.91 mm**. The proposed bench limit is 1 mm. This result depends on the stated mass distribution, tooling alignment and pad flatness.

![Seated pallet and two parallel jaw shoes in the revised locating nest](seated-view.svg)

[Complete seated assembly](seated-assembly.step) · [Near shoe](near-shoe.step) · [Far shoe](far-shoe.step) · [Nest](nest.step) · [Reference pallet](reference-pallet.step)

## Which design to take forward

| Trial | What the calculation or solid intersection found | Decision |
|---|---|---|
| End tab, 1.5 mm lips | A 150 g loaded pallet at 2 m/s² upward acceleration, with a factor of two, applies 3.54 N of vertical design load. At the assumed worst center of mass, the short tab amplifies this to a 23.92 N lower-lip reaction. A one-shoe cantilever calculation gives 47.83 MPa against a provisional 12 MPa limit. | Reject this tab shoe. |
| End tab, 4 mm lips | Stress falls to 6.73 MPa. Its vertical play still permits 3.38° of free pitch. The far edge drops 6.29 mm and the tilted pallet intersects the nest at the nominal seating height. | Thickness alone cannot meet the handoff requirement. |
| Opposing rail shoes and relieved nest | Four underside contact patches straddle the assumed center of mass. The minimum modeled support margin is 7 mm. A conservative whole-load-on-one-pad case gives 1.00 MPa. With ≤0.12 mm pad-height spread the edge-error bound is 0.908 mm. Increasing the spread to 0.35 mm fails at 1.575 mm. | Advance the centered layout to a cold bench trial on a matching parallel fixture. |

The STEP solids for both shoes and the nest were exported, reopened and checked individually. The reopened assembly has four valid solids. The 4 mm outward sweep of each shoe clears both the pallet and the nest at the nominal seated position. The lower shoe clears the relieved nest floor by 1.70 mm. The nest rejected a reversed pallet and a pallet displaced 1 mm in X through detectable solid overlap. These checks use the actual [pallet STEP](reference-pallet.step) shipped with the study. [Numerical results](results.json)

## Interfaces and assumptions

* The nominal board occupies X 0–90 mm, Y 0–50 mm. The projected center of mass of the complete, retained workpiece must be within X 40–50 and Y 20–30 mm. A bare CAD pallet supplies geometry only. A populated board, a cable or a different orientation can shift the center of mass.
* Finished shoe faces are 58.6 mm apart closed and 66.6 mm apart open. The outer face of each shoe has two 1.6 mm-diameter blind pilot bores, 4 mm deep and 7 mm apart. A gripper-side adapter must provide fastener access and suitable thread engagement. The study assumes two parallel shoes. The stock SO-101 has a pivoting jaw and needs a different adapter or mechanism, as well as a recheck of stroke, payload and swept clearance.
* The 30 mm-long shoes have two 3 mm-long lower pads each. The stress calculation assumes a 3 mm effective contact length, a rigid pallet, a factored vertical load and a measured or otherwise justified allowable stress. The 12 MPa value is a screening assumption. Actual contact area, material, print direction, fatigue, mounting hardware, root fillets and wear need qualification.
* The modeled nest allows ±0.20 mm XY placement, 0.20 mm combined face error and ±0.15° yaw. The remaining side margin is about 0.122 mm. The jaw channel has only 0.040 mm remaining vertical insertion margin after the stated tolerances. Measure that allowance on the assembly. For the rail handoff, a rigid support plane is bounded using the worst pad-height spread, minimum support spans and extreme pallet corners. The test covers a level pickup under gravity. Axial slip, acceleration in the horizontal plane, payload retention and a moving arm's collision envelope remain open.

## Reproduce and test

The [parameters](design.json) hold the assumed load, fit, alignment and allowable stress. The [trial](trial.py) runs on the repository's CadQuery 2.8 kernel. From this directory:

```sh
~/.local/share/hardware-splicer/cad-venv/bin/python trial.py --out /tmp/hs-p047-replay
```

The first physical test would use a hand-operated parallel fixture and an inert pallet with the proposed mass and center of gravity. Measure all four bearing heights and the shoe opening, check board retention, then record far-edge height through repeated cold pickup, placement and release on the named nest. Reject an observed edge error above 1 mm. Move the ballast beyond the accepted margin to check that the fixture exposes a bad loading condition. Deliberately offset or reverse the pallet by hand during fit checks. Verify axial retention, fastener integrity and a safe recovery path before proposing powered transfers.

The catalog allows NT$500 for materials, 45 minutes per repeat build, 16 design hours and NT$2,400 for a prototype. The parallel gripper or an SO-101 linkage needs its own quote. At 25 identical sales, adding more than about NT$672 of unbudgeted per-order cost or 67 minutes of labor per order would consume the estimated NT$16,788 profit. No asset purchase, holding-force test, fatigue life or unit assembly time has been measured.
