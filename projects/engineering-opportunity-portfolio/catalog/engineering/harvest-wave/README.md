# Harvest, water and bench trials

Seven digital trials test specific fabrication and procurement decisions. The reports include editable inputs, shipped data, rejected controls and a physical acceptance check for each design. No host, stock sample or bench instrument was measured. Some of the tests use synthetic signals or rigid inert coupons. [Editable cases](cases.json)

Use Python 3.10 or newer and run `python3 verify.py` to regenerate and compare all included artifacts in a temporary directory. To change one input case and write a separate export, use `python3 verify.py --trial P123 --config cases.json --out /tmp/hs-harvest`.

The catalog model has positive unit contribution for all seven and a launch deficit at 25 sales for each. The school tow-net model comes closest, at a NT$175 deficit and 26 modeled sales to recover launch. The flume has NT$754 estimated contribution per unit and a NT$10,250 modeled deficit after 25 sales. Use these figures to prioritize a price or customer trial. The calculations assume paid sales at the target price. [Catalog returns](../../returns.csv)

## P115

[Eight-cell profile](generated/P115/block-mold-projections.svg) · [Ejector schedule](generated/P115/ejector-candidate.csv) · [Results](generated/P115/results.json) · [All trial files](generated/P115/)

**Soil block molding press.** The exported plan has eight 38 mm square upper cells and approximately 40.79 mm exits for a 40 mm depth and 2° draft. With guide runout and two fabrication allowances, the 37 mm plungers retain 0.215 mm minimum side clearance. A 4.5:1 effective lever model gives 37.52 N handle force under the assumed 2.5 kPa equivalent wall breakaway stress and 75% efficiency. The 2:1 control gives 84.42 N against a 60 N screening limit. The revised lever needs 202.5 mm ideal handle travel for a 45 mm ejector stroke. That travel and the unmeasured breakaway load determine whether to keep a self-contained hand press or buy a different capacity tool. The force model assumes uniform wall stress and constant leverage. It does not estimate block fracture. [Commercial 50-cell comparison](https://www.johnnyseeds.com/tools-supplies/seed-starting-supplies/soil-blocking/johnnys-50-cell-commercial-soil-blocker-6225.html)

**Physical check.** Measure tip clearance and peak force using the actual mix. Eject 80 blocks and require at least 75 intact after one watering. Check that the full lever travel clears the operator and surrounding bench.

## P123

[Progressive-bore schedule and flow](generated/P123/flush-progressive.csv) · [Uniform-bore control](generated/P123/flush-uniform-bore-control.csv) · [Results](generated/P123/results.json) · [All trial files](generated/P123/)

**Drip-lateral flush header.** The model solves a steady Darcy loss network for eight lengths with a shared supply and progressively wider drain segments. At the assumed supply curve, 13.6–32 mm manifold bores give worst-case all-open velocities of 0.355 m/s at the lateral ends and 0.376 m/s in the header. The uniform 13.6 mm control yields 0.183 and 0.194 m/s, below the 0.3048 m/s screening gate. Opening each uniform-bore row by itself brings the modeled lateral above 0.517 m/s. This makes staged flushing an alternative to buying varied bores if labor and cleanout time are acceptable. The steady model assumes level lines, no emitter draw and a not-yet-measured supply curve. It omits transient pressure, leakage, fouling and settlement. [UC ANR lateral flushing guidance](https://www.ucanr.edu/site/maintenance-microirrigation-systems/flushing-4)

**Physical check.** Measure actual pipe IDs and open-flow supply behavior. Observe tracer from each of the eight rows, measure exit velocity with eight open and with selected subsets, and inspect closed connections within their component ratings.

## P136

[Net panel dimensions](generated/P136/net-frustum-cut.csv) · [Bead replay](generated/P136/beads-candidate.csv) · [Results](generated/P136/results.json) · [All trial files](generated/P136/)

**School plankton tow net.** The right-cone-frustum panel export locates the developed arcs and sector angle for a 200 mm lip, a 45 mm cup and a 420 mm length. With a specified ±20 µm opening allowance, nominal 200 µm mesh has a 220 µm largest opening. A simplified 100-bead test with a shared, synthetic 3% bypass retains 97% on the candidate and 34% on nominal 300 µm stock. At the tight aperture limit, the estimated clean open area is 1.88 times the inlet area on the finer mesh. This area ratio screens clean geometry and does not predict flow, retention of deformable material, or seam performance. Verify material from the order and add seam allowance according to the sewing process. [USGS tow-net example](https://pubs.usgs.gov/sir/2010/5154/section3.html)

**Physical check.** Gauge a sample of apertures and bench-flow 100 measured inert beads over the declared cutoff. Require at least 90% capture and record seam losses, mesh damage and cup handling.

## P141

[Example binary masks](generated/P141/example-camera-masks.svg) · [Batch summary](generated/P141/batch-summary.csv) · [Results](generated/P141/results.json) · [All trial files](generated/P141/)

**Batch fry counting flume.** An inert silhouette replay exercises four-neighbor segmentation on synthetic snapshots. The area filter accepts 40 singles and defers five visibly merged events in each of ten 50-object batches. Naive connected-component counts understate every batch by five objects. A pair perfectly overlapped in the same view aliases to one object in all 12 controls. This product needs a physical single-object feeder, an independent view, or a documented recheck workflow before it can quote complete counts. The replay assumes one gated snapshot per event and already separated foreground pixels. Camera timing, reflection, target speed and motion blur are unmodeled.

**Physical check.** Run ten blind batches of 50 inert silhouettes through the exact chute. Include clean singles, visible overlaps and full occlusion. Report unresolved events separately, then check actual end-to-end counts with the revised feed or a second view.

## P147

[Power and pressure replay](generated/P147/fault-trials-candidate.csv) · [Example waveform](generated/P147/sample-waveform-candidate.csv) · [Results](generated/P147/results.json) · [All trial files](generated/P147/)

**Aquaculture blower-loss alarm.** A low-voltage dummy pressure-switch contact and independent external-power flag exercise ten plausible timing sequences. With six consecutive low samples at one-second intervals, alarm onset is 5 s after the first low sample in each replay. A 600 mAh battery budget derated to 65% yields 99.50 minutes minimum modeled horn time at an assumed combined 235 mA. A 70 mAh stock control lasts 11.53 minutes and fails the 15-minute screen. The unfiltered switch control alarms during all ten short transients. The model is for supplemental indication. Battery voltage, capacity at service load, changeover, aging and audible level require measurement.

**Physical check.** On a dry rig with the selected switch and supply, drop pressure ten times and require alarm within 30 s. Disconnect external power and confirm continuous audible indication for at least 15 minutes, including when the battery is partially discharged.

## P153

[Marked-article exposure table](generated/P153/inspection-candidate.csv) · [Results](generated/P153/results.json) · [All trial files](generated/P153/)

**Small-lot bean sorting belt.** A five-lane pitch model for dry coffee with 78% occupancy yields a speed window of 51.28–81.82 mm/s for a 25-minute 3 kg batch and 2.2 s minimum viewing time. At 70 mm/s, the model predicts 18.32 minutes, 2.571 s exposure for all 30 marked articles and 3 mm static feed-gate height clearance. The 120 mm/s control lowers the predicted batch time to 10.68 minutes and gives only 1.50 s exposure. Operator recognition, varied orientation, clumping and dynamic lodging are outside this pitch model. Choose a drive that can hold the slower speed under real load before pricing the assembly.

**Physical check.** Run a weighed 3 kg sample with food-contact surfaces and guards in place. Time delivery, tally actual misses on 30 random marked defects under fixed light, and record clumps or lodged beans.

## P156

[Synthetic force check](generated/P156/force-calibration-replay.csv) · [Probe travel envelope](generated/P156/probe-travel-candidate.csv) · [Results](generated/P156/results.json) · [All trial files](generated/P156/)

**Fruit firmness comparison stand.** The design assumes an 8 mm plunger and an 8 mm fixture travel setting. The manufacturer sells an 8 mm tip and stand separately. The synthetic force channel returns within 0.1515 N at three reference loads with an ideal linear scale plus quantization and small code noise. A 550 N/mm frame gives 0.3065 mm maximum travel error in the modeled corner set. The 140 N/mm control gives 0.8387 mm against a 0.5 mm screen. Ten predicted foam peaks span 1.071 N for the revised frame. The flexible frame has a similar span despite failing travel accuracy, so repeatability on the coupon alone is insufficient. The guide model omits eccentric loading, backlash and sample support compliance. The load transducer and actual tip's depth mark still need verification. [TR Turoni 53200 datasheet](https://www.trturoni.com/download-allegato-articolo?id=92) · [UC fruit firmness procedure](https://ucanr.edu/sites/default/files/2013-02/162036.pdf)

**Physical check.** Compare force at three traceable loads, measure the actual tip travel under load within 0.5 mm, and repeat ten penetrations on uniform foam. Check plunger fit and depth witness with the actual fruit procedure before using the fixture for comparisons.
