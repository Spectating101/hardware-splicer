# Install report template — Splice Agent v1

**Purpose:** Document proof that Splice Agent installs and runs on a machine **you did not develop on**.

Copy this file to `INSTALL_REPORT_<hostname>_<date>.md` and fill in after testing.

---

## Report metadata

| Field | Value |
|-------|-------|
| **Tester** | |
| **Date** | |
| **Git tag / commit** | |
| **Machine name** | |
| **OS** | e.g. Ubuntu 24.04 / WSL2 on Windows 11 |
| **KiCad version** | `kicad-cli --version` |
| **Python** | `python3 --version` |
| **Node** | `node --version` |

---

## Install steps followed

Only public docs — no copied `.venv` or pre-built artifacts from dev machine.

- [ ] `git clone https://github.com/Spectating101/hardware-splicer.git`
- [ ] `git checkout __________`
- [ ] `bash scripts/install_splice_v1.sh`
- [ ] `source .venv/bin/activate`
- [ ] `hs-doctor`

**Install script modifications required?** Yes / No — describe:

---

## Doctor output

```
(paste hs-doctor output or attach --json summary)
```

| Check | Pass / Fail |
|-------|-------------|
| Python venv | |
| KiCad CLI | |
| Node / npm | |
| API import | |

---

## Verification (optional hard bar)

- [ ] `INSTALL_DEV=1 bash scripts/install_splice_v1.sh`
- [ ] `make verify-splice-v1` — exit code: ___

Skipped? Reason:

---

## UI demo

- [ ] `make splice-ui-serve` (or `make splice-ui-build` + `HARDWARE_SPLICER_SERVE_UI=1 hs-serve`)
- [ ] Browser: http://127.0.0.1:8787 — Engine **Online**
- [ ] Quick demo OR recent build loaded
- [ ] Gates tab shows real gate data
- [ ] Bench tab accepts measurement (optional)
- [ ] Download zip works

**UI issues:**

---

## API smoke

```bash
curl -s http://127.0.0.1:8787/health
```

- [ ] HTTP 200, `"ok": true`

---

## Manual fixes required

List anything not covered by install script or docs:

1.
2.

---

## Verdict

| | |
|--|--|
| **Install: PASS / FAIL** | |
| **Demo: PASS / FAIL** | |
| **Ready for pilot on this OS?** | Yes / No / With caveats |

**Notes for repo maintainers** (bugs to file):

---

## Attachments

- Screenshot of Gates tab (optional)
- `hs-doctor --json` file (optional)
