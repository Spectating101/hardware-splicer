# Release artifacts

## v1.1.0-alpha.1 (Interface Preview)

**Tag:** `v1.1.0-alpha.1`  
**Notes:** [`RELEASE_NOTES_v1.1.0-alpha.1.md`](../RELEASE_NOTES_v1.1.0-alpha.1.md)  
**Launch:** [`docs/LAUNCH_v1.1.md`](../docs/LAUNCH_v1.1.md)

Publish GitHub prerelease with notes file. Optional asset: sample zip below.

---

## Sample Splice Sprint bundle

**File:** [`sample-splice-sprint-robot-repair-cafe.zip`](sample-splice-sprint-robot-repair-cafe.zip)

Golden **repair café S3** build (`robot_repair_cafe_s3`) — attach to GitHub Releases for reviewers who will not run KiCad.

| Artifact | Purpose |
|----------|---------|
| `PROJECT_PACKAGE.json` | BOM, wiring, gates, build steps |
| `SPLICE_BENCH_SESSION.json` | Bench measurements template / session |
| `BRINGUP_CARD.md` | Operator bring-up card |
| `WIRING_GUIDE.md` | Wiring narrative |
| `build_compilation/` | KiCad carrier + compile evidence |

Generated from a passing `verify-splice-loop` artifact on dev-linux. Regenerate:

```bash
make verify-splice-loop
cd /tmp/hs_splice_golden_verify/robot_repair_cafe_s3
zip -r sample-splice-sprint-robot-repair-cafe.zip .
```
