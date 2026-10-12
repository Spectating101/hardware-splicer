# Device diagnostic deliverables — local verification, 2026-10-12

Implementation branch: `agent/hs-competitive-integration`.
Software/CI candidate: `74848d2586df46704bd4df72ead2f8daa10bd57d`.
The full Python run covered the same Python source at `6a7b233c`; the subsequent
commit changes only CI library provisioning and its documentation.

No branch push, main merge, GitHub workflow execution, physical operation or
vendor contact is claimed by this record. Historical Astra/SPI releases are
unchanged. The result is a catalog **compile-only diagnostic proposal**, not
authorized hardware or a finished sensor application.

## Implemented

- Stateless firmware export from the existing device spec/plan and module library.
- Explicit GPIO tracing, including reversed wires, shared buses and renamed IDs;
  no fallback GPIOs or guessed peripheral bus merging.
- Deterministic source ZIP with input/plan/source hashes and declared address
  alternatives. Client-provided findings and authority cannot grant export.
- Device-page download through the real proxy/API, with stale-edit, warning,
  invalid-input and upstream-error handling.
- Separate pinned compiler execution and downloadable compiler bundle, requiring
  exit zero and both nonempty ELF/BIN artifacts.
- CI real/mock browser matrix and compiler job. The broader job explicitly
  provisions KiCad 9 lookup libraries; compiler/API dependencies are isolated.

The verified-interface PlatformIO backend, project stores, authority model and
release semantics were not changed. The sketch does not automatically start an
I2C scan. A later serial command can drive a bus probe; it is not authorization.
ACKs are not device identity, functional readings or physical verification.

## Local results

| Check | Result |
| --- | --- |
| Full Python suite | 3498 passed, 13 skipped, 105 warnings; 730.76 seconds |
| Real product API browser flow | 27 passed; zero retries/skips/failures/flakes |
| Broader studio-fixture browser suite | 100 passed; zero retries/skips/failures/flakes |
| ESP32 compilation | Two fresh successful runs, ELF and BIN produced |
| Production frontend | Both isolated builds passed; typecheck and changed-file ESLint passed |
| Contracts and workflow | Engineering UI contracts, shell/JS syntax, actionlint and whitespace checks passed |

Actionlint 1.7.7 ran without ShellCheck, which was unavailable. CI is configured
but not yet remotely exercised. Library provisioning follows the existing
repository KiCad 9 PPA approach; installation on a fresh GitHub runner remains
part of that pending remote check.

The source ZIP is byte-identical across compiler runs. Binary reproducibility is
**not** asserted: fresh build directories produced different ELF/BIN hashes.
Compilation only establishes that this software target builds; both authority
flags remain false and physical correctness remains UNPROVEN.

## Retained local artifacts

Raw artifacts are intentionally ignored, not silently presented as published
evidence. Their paths and hashes identify this local run; the workflow will
upload corresponding artifacts when explicitly published and run.

- Full Python log: `.cache/hardware-splicer/deliverables-pytest-wu18sd/full-python.log`
  — SHA-256 `553f5df820c7179250820986509201baa13396f2863a01610ba9e34d9f2fd7f7`.
- Real browser JSON: `.cache/hardware-splicer/frontend-verify-JGGUH9/playwright-report.json`
  — SHA-256 `4094ec110674a300ccac4945835a4bd8b9b5463801684a23e3a13aaea693a3ba`.
- Broader browser JSON: `.cache/hardware-splicer/frontend-verify-JBfwEm/playwright-report.json`
  — SHA-256 `0bc5a759baa9ee403ad86804cbd0f04f1797efa64fa6756a0cf7fb9f5f89be43`.
- Final compiler directory: `.cache/hardware-splicer/device-firmware/device-firmware-yjian6j1/`.
  `COMPILE_RESULT.json` SHA-256
  `3dbcd24384151214a54a00eff05c90533d087072664c509719be2a8290d85c13`.
- Source ZIP SHA-256:
  `e26a56bcaf861e64f434b6732ed1446e20dec3442de388a78dc2cbd3906f7e7b`.
- Compiled proposal ZIP SHA-256:
  `e86f994a4202747c349b1b2e98b0e6a6487125cf847787fc21d0948779581dd2`.
  All five outer members pass ZIP integrity checks. The report binds source,
  compiler log and binaries; the source archive remains unaltered.

## Reproduce and use

See [DEVICE_FIRMWARE.md](../DEVICE_FIRMWARE.md) for the UI flow, exact commands,
dependencies, supported scope and physical-use limits. The end-to-end
verification checklist drove testing through UI → proxy → API → actual ZIP,
rather than crediting source generation alone.

New implementation commits:

- `f2845d9c`: build compile-only firmware proposals from device wiring.
- `dd7a5734`: download wiring-bound diagnostic source through the device page.
- `6a7b233c`: gate deliverables with real API and compiler checks.
- `74848d25`: provision KiCad lookup libraries for browser CI.

The user's push choice is still outstanding. Retain the no-push hold unless
they explicitly authorize publishing the integration branch. No historical
commit or worker draft needs rewriting, reapplying or deletion.
