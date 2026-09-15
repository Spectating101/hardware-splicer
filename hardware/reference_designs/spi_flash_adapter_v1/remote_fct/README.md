# Remote FCT campaign

This directory converts the revision-0.2 reference design into a provider-neutral physical
execution request. The deterministic campaign builder binds six production roles—schematic,
fabrication archive, BOM, pick-and-place, assembly drawing and read-only test utility—to
individual SHA-256 identities and to the existing Hardware Splicer remote-return contract.

Build from the reference-design directory:

```bash
python3 build_remote_fct_campaign.py --output out/spi-flash-adapter-v1-remote-fct.zip
```

The output is suitable for capability/quotation review. Its production artifact set is
complete, but `fabrication_release_ready`, `power_on_ready` and physical authority remain
false. Contact details, credentials, payment details and vendor model bytes are excluded.

The first host transaction is intentionally narrow. `scripts/run_spi_read_only_jedec_id.py`
defaults to a no-device dry run. Live use requires the campaign/article/operator identities
and bench authorization before opening the transport; it then configures mode 0, 8-bit,
MSB-first, active-low-CS operation while JP1 remains open and pauses until the operator bridges
JP1 and types `ENABLED`. The single full-duplex transfer is fixed to `9F 00 00 00` and the
clock is capped at 5 MHz. A returned JSON log still requires raw waveform evidence, server
attestation and revision-bound import.
