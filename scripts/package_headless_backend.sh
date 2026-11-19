#!/usr/bin/env bash
# Bundle a committed revision for a source-backed editable install.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
revision="$(git -C "$root" rev-parse --verify --end-of-options "${1:-HEAD}^{commit}")"
out_dir="${2:-$root/outputs/release-handoff}"
name="Hardware-Splicer-${revision:0:12}-backend"
mkdir -p -- "$out_dir"
tmp="$(mktemp "$out_dir/.$name.XXXXXXXX")"
trap 'rm -f -- "$tmp"' EXIT

# Keep registered sources, fixtures, supplier datasheets and operator tools.
# Only historical review captures and saved evaluation runs are left out.
git -C "$root" -c tar.umask=0002 archive --format=tar --prefix="$name/" "$revision" -- . \
  ":(exclude)review-ui" \
  ":(exclude)docs/external_assessment/proof/astra_runs" \
  ":(exclude)apps/circuit-ai/eval/live_model_probe" \
  ":(exclude)apps/circuit-ai/eval/real_browsed_case" |
  zstd --quiet -10 -T1 --long=27 --stdout > "$tmp"
chmod 644 "$tmp"
mv -f -- "$tmp" "$out_dir/$name.tar.zst"
printf "%s\n" "$out_dir/$name.tar.zst"
