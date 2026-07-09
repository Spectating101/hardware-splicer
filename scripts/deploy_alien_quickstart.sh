#!/usr/bin/env bash
# One-shot alien quickstart from optiplex → DESKTOP-FGEDHGV WSL.
# Usage: bash scripts/deploy_alien_quickstart.sh [git-ref]
# Default proof tag: v1.1.0-alpha.12 (vision-assist in quickstart bar)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REF="${1:-v1.1.0-alpha.12}"
HOST="${HS_ALIEN_HOST:-desktop-fgedhgv}"
ARCHIVE="/tmp/hs-alien-quickstart.tar.gz"

echo "==> archive $REF"
git archive "$REF" | gzip > "$ARCHIVE"

echo "==> scp to $HOST"
scp "$ARCHIVE" "$ROOT/scripts/agent_quickstart_verify.sh" "$HOST:"

echo "==> run quickstart in WSL"
ssh "$HOST" "wsl --distribution Ubuntu-24.04 -- bash /mnt/c/Users/user/agent_quickstart_verify.sh /mnt/c/Users/user/hs-alien-quickstart.tar.gz"

echo "deploy_alien_quickstart: PASS ($REF on $HOST)"
