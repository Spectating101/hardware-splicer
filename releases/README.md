# Release artifacts

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
