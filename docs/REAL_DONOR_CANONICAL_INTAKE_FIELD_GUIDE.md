# Hardware Splicer real donor intake — first physical device

**Scope:** This is a field data handoff into the *existing* canonical Hardware-Splicer repair intake pipeline, not an autonomous repair or proof the physical device works.

## First owned device: basic 5V USB fan (not mains, not an uninspected lithium gadget)

Obtain a personally owned or explicitly authorized nonmains low-voltage 5V USB fan with an identifiable fault. The first run does **not** require buying a particular model and does not assume any donor hardware already exists.

Download the latest verified **six-workorder / six-blank-input-template** CI artifact from [PR #265](https://github.com/Spectating101/hardware-splicer/pull/265). The USB-fan bundle contains:

- \`FIELD_WORK_ORDER.json\`: immutable source work order with step sequence, evidence/measurement gates and safety stops.
- \`HUMAN_BENCH_CARD.md\`: human-readable source service path; every physical step is initially unperformed.
- \`DONOR_INPUT_TEMPLATE.json\`: one blank, work-order SHA-bound record for the exact device you actually own.

### Field protocol — without energizing

1. Identify the model from a redacted equipment nameplate. Record the **actual** symptoms as observed, not the source example's hypothetical symptoms. Do not upload passwords, serials, IMEIs, accounts or owner messages.
2. Obtain permission to repair/inspect the device; record this in a privately stored owner/consent receipt. This receipt's **SHA-256** can be checked but cannot establish the legal authenticity of permission.
3. Collect one redacted, genuinely original device photo and one original fault-observation file, plus the consent record. Keep all three in a **private evidence directory outside Git/source control**; never upload them into public repository CI.
4. Fill \`device_model_redacted\`, \`device_symptoms_observed\`, \`reported_condition\` and the \`operator_attestation\` booleans on the blank template from actual observation. Enter each original file's relative path within the private evidence directory and SHA-256 digest.
5. Run the source-canonical bridge. It checks the work order identity, original evidence file hashes and operator assertions, then writes the normal HS \`PROJECT_INTAKE.json\` using \`hardware_splicer.repair_intake.apply_repair_intake_context\`.

Run from this repository root with Python 3.12 and its declared package dependencies (\`pip install -e .\`):

\`\`\`bash
python -m scripts.bridge_hs_real_donor_canonical_intake_001 \
  --root . \
  --pilot usb_fan_contact_driver_repair \
  --workdir /path/to/workorder/usb_fan_contact_driver_repair \
  --donor /path/to/private/DONOR_INTAKE.json \
  --files-root /path/to/private/original_evidence \
  --output /path/to/private/hs_real_device_intake
\`\`\`

Verify the compiled handoff with \`python -m scripts.verify_hs_real_donor_canonical_intake_001 --root . --pilot usb_fan_contact_driver_repair --workdir /path/to/workorder/usb_fan_contact_driver_repair --donor /path/to/private/DONOR_INTAKE.json --output /path/to/private/hs_real_device_intake --acceptance /path/to/private/ACCEPTANCE.json\`.

The resulting **normal HS \`PROJECT_INTAKE.json\`** can be read through \`hardware_splicer.project_intake.load_project_intake\`; only actual operator-observed faults are carried. \`available_parts\` stays empty until genuine individually identified components are physically verified. There is no automatic disassembly, repair, power-on, firmware flashing, flight, fabrication, commercial valuation or sale authorization from this software. The intake is not yet a service outcome.

### What makes it an actual recovered product?

For the fan, the bench-card's original disconnected continuity inspection and current-limited motor checks must first be cleared by a trained operator. Then capture actual rated voltage, measured voltage/current, harness resistance, motor winding resistance, before/after real-operation evidence, and human acceptance for a safely reassembled guarded fan. A functional report must link source files and genuinely observed values. **A clean intake or signed hash is never itself a repair.**

For phones and laptops, preserve privacy and battery safeguards; stop at an unsafe damaged lithium pack or a model with undocumented repair methods. For junk drones, keep all propellers removed for any permitted bench test, use vendor-supported SITL, and never claim permission for an actual outdoor flight.

### CI and limitations

GitHub Actions uses explicitly **synthetic** files to test only transport integrity and normalizer integration, rejects adversarial source/authority claims, and publishes **blank templates only**, not fake owner photos or pretend physical repairs. Even true SHA receipts do not prove file authenticity, consent, equipment ratings or a technician's measurements.

Next actual step is a **real donor with operator evidence**. Without that physical input, development should shift to improving diagnostic tools or acquiring a device rather than repeating another round of synthetic "repaired" examples.
