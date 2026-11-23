# SPI virtual verification

Hardware Splicer's SPI virtual-verification layer provides a deterministic software-only
check between document-grounded engineering reasoning and eventual bench evidence. It is
intentionally useful without a live frontier-model run.

## What it verifies

`hardware_splicer.spi_virtual_verification` currently checks:

- the required SPI signal-direction contract: SCLK/MOSI/CS# host-to-DUT and MISO DUT-to-host;
- direct-drive compatibility against a source-derived DUT pin absolute-maximum rule;
- translator channel topology for the required three-forward/one-reverse mapping;
- exact translator identity/package/OE/partial-power closure;
- DUT-supply range, current-budget, and sequencing closure;
- requested SPI clock against a supplied candidate timing/load boundary;
- explicit source/claim identities for critical verification inputs; and
- an optional candidate-bound simulator result.

The published raw-document v4 boundary is available as a built-in candidate fixture. It is
expected to remain `blocked`: the document evidence supports the topology and rejection of
direct 3.3 V drive, but exact translator implementation, DUT supply, timing/load budget, and
candidate-bound simulation are still unresolved.

## Fault corpus

Run the zero-inference adversarial corpus with:

```bash
python scripts/run_spi_virtual_verification.py --case corpus
```

The initial corpus injects four faults/boundary changes:

1. direct 3.3 V host drive;
2. reversed MISO direction;
3. one SN74AXC4T245 represented as two shared two-channel direction groups for the 3+1 SPI mapping;
4. removal of the DUT absolute-maximum claim provenance.

Expected behavior is deterministic: the first three unsafe/incompatible candidates fail,
while missing provenance blocks promotion rather than fabricating support.

## Authority boundary

A virtual-verification pass means only that the supplied candidate and attached simulator
results satisfied the encoded software checks. Every result hard-codes:

- `measured_evidence_present=false`;
- `physical_correctness=UNPROVEN`;
- `fabrication_ready=false`;
- `power_on_ready=false`;
- `physical_authority_granted=false`; and
- `authority_effect=none`.

Candidate input cannot override those fields.

Simulation is not measurement. An ngspice, analytical, IBIS, protocol, or other model result
may increase software confidence and can reject a candidate, but it cannot establish real
assembly identity, parasitics, workmanship, silicon behavior, or safe physical operation.

## Astra resource policy

Astra is not required to develop, run, or regression-test this verifier. The intended order is:

1. freeze deterministic checks and adversarial fixtures;
2. bind an exact implementation candidate and real model inputs where available;
3. run static/simulation verification offline;
4. validate the full repair-loop plumbing with scripted fixtures;
5. only then consider one bounded Astra run in which the model receives verifier failures,
   proposes a canonical repair, and the deterministic verifier reruns.

Do not spend live-model allowance on verifier plumbing, simulator integration, fixture tuning,
or regression testing.

## Next simulation tranche

Hardware Splicer already has `electrical_simulation.py` and the canonical ngspice execution
boundary. The next integration should reuse those components rather than invent a second
simulator. SPICE credit should remain blocked until an exact candidate/netlist and defensible
part/model parameters exist. Synthetic unit-test models must be labeled synthetic and must not
be presented as manufacturer-grounded evidence.
