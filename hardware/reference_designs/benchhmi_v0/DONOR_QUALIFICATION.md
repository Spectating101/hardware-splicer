# PF-002 real donor qualification

Use this against **one exact Flytech POS462**. Do not generalize the result to a lot.

## Record first

- purchase price and shipping;
- seller/listing reference;
- external serial/asset tag;
- motherboard identity — **B91 required**;
- photos of front/rear/labels and the board identity when safely observable;
- inspection start/end time.

## Acceptance sequence

1. Visual inspection — reject swelling, burn damage, damaged mains inlet/cable, severe corrosion or evidence requiring PSU repair.
2. Cold boot repeatedly from full power removal.
3. LCD inspection — usable brightness, no unacceptable lines/large defects.
4. Touch — calibration and repeated recognition after cold boots.
5. Ethernet — stable link and transfer.
6. USB — test every port required by the product contract.
7. COM — loopback or known-device transaction on every retained required COM port.
8. Storage — identify current media; replacement SSD is expected rather than trusted by age.
9. Thermal — run a representative terminal/network workload and record instability/overheating.
10. Power system — external observation only. Reject abnormal noise, odor, overheating, unstable behavior or anything requiring mains-side repair.

## Evidence rule

The real record must use:

```json
"simulated": false
```

and every required check must contain both `"state": "PASS"` and a concrete evidence note.

Run:

```bash
python experiments/product_factory/qualify_pf002_donor.py \
  experiments/product_factory/fixtures/benchhmi_pos462_real_template.json
```

A passing record qualifies only that exact donor for continued PF-002 engineering. It does not establish batch yield or supply depth.
