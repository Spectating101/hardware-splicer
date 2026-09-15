# Request for quotation: SPI flash adapter design, prototype, and validation

Status: **prepared only — not submitted, accepted, ordered, or authorized**.

## Objective

Design, assemble, and independently test a small adapter that permits a 3.3 V standard-SPI
controller to perform a read-only JEDEC `0x9F` transaction with a 1.8 V W25Q128JW-family flash
device through a TXU0304-family fixed-direction translator.

The engagement must produce a reviewable engineering design and serialized physical prototypes.
It must not silently treat the family-level candidate as an approved exact implementation.

## Frozen starting boundary

- Hardware Splicer project: `hs-astra-rawdoc-v4-20260913-1`, revision `6`.
- Candidate snapshot: `sha256:b7c724e0561d4ec8ab21b7ad4e869256c5cca2f80416d1f07bd020164c152272`.
- Physical packet: `physical-validation-fdd10770454d7a84`.
- Host declaration: 3.3 V standard SPI; SCLK, CS#, and MOSI/IO0 are host-to-DUT;
  MISO/IO1 is DUT-to-host.  The exact controller remains unresolved.
- DUT evidence: Winbond W25Q128JW Revision G,
  `sha256:4d065361637dcc10554a6384516e9e98cc000c986b03be874d4b5670b70e275e`.
- Translator evidence: TI TXU0304 Revision A,
  `sha256:f6f6178296b8d497d3706ea7766633b62f799cfe830659a2dcfd09c79bfa71dc`.
- The TXU0304 is a preferred **family-level** candidate only.  No orderable MPN, package,
  regulator, connector, protection network, schematic, or PCB is pre-approved.

The complete source-bound requirements, alternatives, decisions, blockers, and claim locators are
published in the repository's frozen Astra v4 engineering package.  Raw manufacturer document
bytes are not redistributed in this request; use the official source locators and report the
exact document revisions used for design review.

## Requested engineering work

1. Resolve an exact, currently procurable W25Q128JW orderable device and package and document its
   package-specific pinout.
2. Resolve an exact TXU0304 orderable MPN/package and confirm the 3-host-to-DUT plus
   1-DUT-to-host mapping.
3. Select and justify the local 1.8 V rail, input range, current budget, sequencing, decoupling,
   protection, and deterministic output-enable-low behavior.
4. Define the 3.3 V controller/test interface and its measured voltage/timing envelope.
5. Complete VIH/VIL/VOH/VOL, propagation-delay, load, rise/fall, and SPI clock budgets.
6. Produce the schematic and PCB with accessible rail/signal test points and design-for-test
   provisions.
7. Run independent electrical review, ERC, DRC, DFM, DFA, and DFT checks.
8. Assemble serialized prototypes and execute the attached eight-gate physical test request in
   prerequisite order.

## Required design deliverables

- editable native schematic and PCB sources plus PDFs;
- ERC and DRC reports with tool/version identity;
- fabrication archive/Gerbers and drill files;
- BOM with manufacturer name, exact MPN, description, quantity, and approved substitution rule;
- pick-and-place/centroid file and assembly drawings;
- design calculations for power, logic levels, timing, loading, and protection;
- test-point/fixture definition;
- source and reproducible build instructions for read-only test firmware;
- DFM/DFA/DFT review records;
- SHA-256 manifest covering every delivered artifact;
- reviewer identity, review scope, date, and exceptions.

## Required physical return

Use `REMOTE_PHYSICAL_HANDOFF.zip` as the test contract.  For each executed gate, return original
instrument/camera files, measured values, acceptance criteria, operator identity, instrument and
calibration identities, assembly revision, serial number, capture time, SHA-256, and byte size.

The first powered command is limited to read-only JEDEC ID `0x9F`.  WREN, status writes, program,
and erase operations are outside scope.  Failures must be returned with their raw captures.

## Quote response requested

Please separate price and lead time for:

- design review and exact component closure;
- schematic and PCB design;
- DFM/DFA/DFT and fixture engineering;
- component procurement and prototype assembly;
- functional/electrical/thermal execution of the attached test contract;
- delivery of all editable design files and original raw evidence;
- one correction/retest cycle after a failed first article.

Also identify any requested deliverable or raw-export requirement the provider cannot supply.

## Authority

This RFQ requests capability and pricing only.  It does not authorize design acceptance,
component substitution, purchasing, fabrication, power-on, destructive testing, or publication.
Any later authorization must identify the exact revision and artifact hashes it covers.
