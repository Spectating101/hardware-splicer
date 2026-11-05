# Actual Optiplex native signed ERC evidence — 2026-11-05

This directory contains a real native KiCad 9.0.2 Electrical Rules Check
performed through the new fixed-input signed HS worker using *temporary*
test identity/enrollment. This was not a mock, GitHub-hosted job or persistent
workstation enrollment.

The artifacts are:

- public_identity.json — disposable Ed25519 public key, not a private key
- receipt.json — signed source/output provenance, task and non-approval flags
- erc.json — unmodified native KiCad ERC JSON for the committed reference design

Input SHA-256: 6f322855430c53bcac5b65b23ec2a271ae45203f894b9775339eb9ae04b5faf3

Report SHA-256: 34bf1edc414e34ff709d725aedc2de173447370b8df36b4927def232e048e45a

Source commit: f7bbc37a51adef74f4c4b703e1451a8e78928fdd

KiCad: 9.0.2

Findings: **40 warnings, zero errors, zero exclusions**. All forty are
lib_symbol_issues, arising from the isolated runner's symbol-library
configuration. This does NOT establish electrical correctness.

To independently check the public-key signature, report hash, source bytes,
findings and no-physical-authority flags:

    python3 -m pip install -e '.[worker]'
    python3 scripts/hs_optiplex_worker.py verify-bundle --bundle evidence/github_signals/optiplex_signed_erc_20261105 --workspace .

A passing signature establishes that whoever controlled the included public
key's corresponding private key signed this result. An ephemeral test key
does not prove host-specific hardware identity or an independently trusted
operator enrollment. The private key is intentionally not in this repository.

The live persistent enrollment, cross-host signed transfer and scheduling
capability remain separate future acceptance gates.
