# HS signed Optiplex KiCad worker — 2026-11-05

This is an opt-in **read-only engineering worker** on the existing authorized
Optiplex. It is independent of PR #283's GitHub Actions controller and does not
make the Optiplex an unrestricted GitHub self-hosted runner.

## Scope and engineering evidence

- The only allowed task is kicad_erc_fixed on the committed HS SPI-flash
  adapter schematic. The exact Git source revision and input bytes are hashed.
- Official installed KiCad v9 CLI processes a temporary copy and returns its
  native JSON ERC report, preserving both errors and warnings.
- Ed25519 signs the worker receipt, including the source SHA, input SHA-256,
  output SHA-256, source path, findings, versions and lack of device authority.
- Independent verification checks the public-key signature, source pin,
  report hash and diagnostic counts. Historical evidence remains verifiable
  after the worker is revoked.
- Execution requires an accepted signed heartbeat within 120 seconds. Signed
  heartbeats enforce monotonic sequence, receiver-time validity, explicit
  enrollment, revocation and capability matching.
- The private key stays in an operator-owned 0600 file outside GitHub. A
  public key is approved explicitly; it cannot grant physical authority.

## Authorized on-device commands

From a trusted checkout, install optional worker dependencies:

    python3 -m pip install -e '.[worker]'

Choose persistent paths *outside* the Git checkout:

    KEY_DIR="$HOME/.config/hardware-splicer/readonly-worker"
    LEDGER="$HOME/.local/state/hardware-splicer/readonly-worker"

Generate a private/public Ed25519 pair, refusing an existing key directory:

    python3 scripts/hs_optiplex_worker.py identity --key-dir "$KEY_DIR"

Approve the generated public identity for the fixed ERC capability:

    python3 scripts/hs_optiplex_worker.py enroll --ledger "$LEDGER" --public-key "$KEY_DIR/identity.json" --approve

Prove key possession and inspect the enrolled worker:

    python3 scripts/hs_optiplex_worker.py heartbeat --ledger "$LEDGER" --key-dir "$KEY_DIR"
    python3 scripts/hs_optiplex_worker.py status --ledger "$LEDGER"

Dry-run first, then explicitly execute the fixed schematic analysis:

    python3 scripts/hs_optiplex_worker.py run --ledger "$LEDGER" --key-dir "$KEY_DIR" --workspace .
    python3 scripts/hs_optiplex_worker.py run --ledger "$LEDGER" --key-dir "$KEY_DIR" --workspace . --execute

Use the actual returned request ID to verify the signed receipt:

    python3 scripts/hs_optiplex_worker.py verify --ledger "$LEDGER" --workspace . --request-id hs-local-0123456789abcdef

To revoke a worker identity:

    python3 scripts/hs_optiplex_worker.py revoke --ledger "$LEDGER" --worker-id hs-node-0123456789abcdef --approve

The hex IDs shown are illustrative and should be replaced by actual values.
Never paste or upload a private key. Deletion of a private key is not itself
the registry's revocation mechanism.

## Reality check

The authorized Optiplex has KiCad CLI 9.0.2 and previously produced 40 ERC
findings on a temporary copy of the reference schematic. Many findings are
related to the local symbol-library configuration. This exploratory command
was NOT an end-to-end signed-worker execution and does not prove the design is
correct or production ready.

New worker tests exercise signing, enrollment, heartbeat replay/freshness,
revocation, fixed-task selection, native JSON schema, provenance and artifact
hash rejection. Real persistent enrollment and signed ERC job execution still
require a separately verified authorized on-device activation.

## Safety and next integration

The repo remains public; enabling a generic self-hosted GitHub Actions runner
on the Optiplex could expose it to untrusted pull-request code. This branch
does not do that. It neither creates a remote daemon nor joins this worker to
PR #284's remote scheduler. It does not grant equipment or fabrication access.

Next acceptance gate: actual signed fixed ERC execution, evidence collection,
then separately authenticated transport, expiring leases and a two-backend
cloud/Optiplex allocation benchmark.
