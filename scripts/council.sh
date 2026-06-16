#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export COUNCIL_PROJECT_ROOT="$ROOT"
export COUNCIL_HUB_ROOT="/home/phyrexian/.codex/plugins/cache/optiplex-marketplace/council-copilot-hub/0.2.0"
exec bash "/home/phyrexian/.codex/plugins/cache/optiplex-marketplace/council-copilot-hub/0.2.0/scripts/council.sh" "$@"
