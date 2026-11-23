# Cluster / SSH verification

Use your student cluster when local disk is tight or you want a nightly full run.

## One-time setup on the cluster

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
export HARDWARE_SPLICER_TMP_ROOT=/scratch/$USER/hardware-splicer   # or your NFS mount
bash scripts/setup_demo.sh
```

Copy `.env.local` to the cluster only if you want live Qwen vision probes (`HARDWARE_SPLICER_RUN_VISION_LIVE=1`).

## Full verify (matches professor path + explore)

```bash
export HARDWARE_SPLICER_TMP_ROOT=/scratch/$USER/hardware-splicer
bash scripts/cluster_verify.sh
```

## Optional profiles

| Env | Effect |
|-----|--------|
| `HARDWARE_SPLICER_RUN_VISION_LIVE=1` | Runs live vision test (needs Qwen key in `.env.local`) |
| `HARDWARE_SPLICER_CLUSTER_FULL_APPS=1` | Also runs `make test-apps-full` (torch stack, ~10+ min) |
| `HARDWARE_SPLICER_SKIP_CADQUERY=1` | Faster setup when STL rendering is not needed |

## Cron example (weekly)

```cron
0 3 * * 0 cd ~/hardware-splicer && git pull && HARDWARE_SPLICER_TMP_ROOT=/scratch/$USER/hardware-splicer bash scripts/cluster_verify.sh >> ~/hs-verify.log 2>&1
```

## GitHub Student synergy

- **Actions** = canonical green on every push (lightweight)
- **Cluster** = heavy explore + optional full apps + vision
- **Codespaces** = occasional demo clone when laptop disk is full
