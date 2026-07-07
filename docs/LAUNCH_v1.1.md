# Launch runbook — v1.1.0-alpha.1 (Interface Preview)

**Goal:** Ship a deployable, demonstrable alpha — not more scope.

**Tag:** `v1.1.0-alpha.1` @ `c3f6589` (or later `main` after launch polish commits)

**One-liner for strangers:**

> Self-hosted hardware bring-up workbench: inspect design, BOM, and fab readiness **before** fabrication or power-on.

---

## 1. Verify (local, ~15 min)

```bash
git pull
source .venv/bin/activate
make verify-product-v1
make verify-ui-interface-smoke   # needs API on :8787 in another terminal
```

Optional full bar:

```bash
make verify-product-internal
```

---

## 2. Deploy (single machine)

**Demo / pilot (recommended):**

```bash
make splice-ui-serve
# open http://127.0.0.1:8787
```

**Production-style (systemd):**

1. `bash scripts/install_splice_v1.sh`
2. `make splice-ui-build`
3. Copy `deploy/systemd/hardware-splicer.service.example` → enable with `HARDWARE_SPLICER_SERVE_UI=1`
4. Optional: `deploy/nginx/splice-agent.conf.example` for TLS + API key on LAN/VPN

See [`deploy/DEPLOY.md`](../deploy/DEPLOY.md) and [`OPERATIONS_RUNBOOK_v1.md`](OPERATIONS_RUNBOOK_v1.md).

---

## 3. GitHub Release (prerelease)

Tag already pushed. Publish assets:

```bash
gh auth login   # once
gh release create v1.1.0-alpha.1 \
  --title "v1.1.0-alpha.1 — Interface Preview" \
  --notes-file RELEASE_NOTES_v1.1.0-alpha.1.md \
  --prerelease
```

Attach optional sample zip (v1.0.2 repair café case still valid for gates story):

- `releases/sample-splice-sprint-robot-repair-cafe.zip`

---

## 4. Five-minute demo (pilots / reviewers)

Follow [`DEMO_5_MIN_UI.md`](DEMO_5_MIN_UI.md).

**Must show:**

1. Home → readiness pitch
2. Quick demo → **Readiness verdict** hero (hold / OK)
3. **Design verify** → KiCanvas + BOM + fab coverage
4. Gates → bench measurement
5. Download zip

Record screen for outreach if possible.

---

## 5. Outreach kit

| Send | Path |
|------|------|
| Entry | [`GITHUB_START_HERE.md`](GITHUB_START_HERE.md) |
| Before/after | [`COMPARISON_DEMO_CASE_robot_repair_cafe.md`](COMPARISON_DEMO_CASE_robot_repair_cafe.md) |
| Pilot offer | [`OFFER_SPLICE_BENCH_KIT_v1.md`](OFFER_SPLICE_BENCH_KIT_v1.md) |
| Release notes | [`RELEASE_NOTES_v1.1.0-alpha.1.md`](../RELEASE_NOTES_v1.1.0-alpha.1.md) |

**Ask:** “Would a readiness package on your next prototype reduce handoff chaos before fab or power-on?”

Track conversations in [`EXTERNAL_PROOF_CHECKLIST.md`](EXTERNAL_PROOF_CHECKLIST.md).

---

## 6. Launch complete when

- [ ] `make verify-product-v1` green on release commit
- [ ] GitHub prerelease `v1.1.0-alpha.1` published with notes
- [ ] One machine deployed via `splice-ui-serve` or systemd
- [ ] 5-min demo recorded or run live once
- [ ] ≥1 external conversation with kit above

---

## 7. After launch (only if pilots pull)

- JLC enrich toggle, donor photo wizard, native Windows installer
- Mermaid offline fallback
- Readiness PDF export for handoff

Do **not** start these until a pilot blocks on them.

---

*Last updated: July 2026 · v1.1 interface preview launch*
