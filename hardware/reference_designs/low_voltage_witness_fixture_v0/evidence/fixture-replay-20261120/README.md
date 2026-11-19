# Reproducible SOFTWARE experiment evidence — 20 November 2026

**Classification: TEST_FIXTURE. No electronic components, current source, multimeter, INA228 carrier or physical operator were used.**

This bundle is the output of:

```bash
python3 verify_and_replay.py --pl-root /absolute/path/to/policy-lab --out /new/output-directory
```

with HS revision `feature/low-voltage-witness-fixture-20261120`, Policy Lab revision `feature/measurement-investigation-20261120`.

- `verification.json` — evidence SHA-256: `57c40d7582ce420b70d019d0f9113d5ec6df4d233dd715778ced685cc7b14a00`.
- `spice-result.txt` — 5.0 V source, assumed 50 mΩ fuse/contact, 15 mΩ Adafruit shunt, 10 mΩ reference shunt, 10 Ω load. 2.462918 W at J2.
- `primary/` — 183 simulated raw INA228 register capture samples processed by actual HS decoding/capture code; the device ID and clock are intentionally synthetic.
- `reference-fixture.csv` — separately constructed analytical reference shunt path; **not** a DMM export.
- `policy-lab-intake/` — original CSV bytes, normalized intervals, conversion, manifest and unchanged PLRS-6 receipt.
- `station/` — quantitative station design, wiring and unresolved parts.

Receipt SHA-256: `ea0fc697d487af95c2045fe7e0d2a28c776c90ed2db7311575f873efec3d016b`. All raw-byte files are marked `-text` in the new repository `.gitattributes` to prevent Git line-ending normalization from invalidating the hashes.

Two separate fresh runs produced identical verification JSON, station specification, source CSV bytes and PL intake receipt. This establishes software determinism, not independent physical reproduction.

**All physical safety, electrical assembly, calibration, device identity, clock-synchronization and causality gates remain open**; read [BUILD_HOLD.md](../../BUILD_HOLD.md).
