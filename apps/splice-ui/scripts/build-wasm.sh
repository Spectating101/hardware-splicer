#!/usr/bin/env bash
# Rebuilds src/components/wasm/fielddeck_chains.wasm from wasm/fielddeck-chains (Rust).
# The built module is committed, so `npm run build` never needs Rust; run this after editing
# the crate, and `--check` to confirm the committed module matches the source.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
crate="$here/wasm/fielddeck-chains"
out="$here/src/components/wasm/fielddeck_chains.wasm"
target="${CARGO_TARGET_DIR:-$crate/target}"
command -v cargo >/dev/null || { echo "cargo not found: install Rust (rustup) to rebuild the module" >&2; exit 2; }
rustup target list --installed 2>/dev/null | grep -qx wasm32-unknown-unknown \
  || { echo "missing target: rustup target add wasm32-unknown-unknown" >&2; exit 2; }
cargo test --quiet --manifest-path "$crate/Cargo.toml"
CARGO_TARGET_DIR="$target" cargo build --quiet --release --target wasm32-unknown-unknown --manifest-path "$crate/Cargo.toml"
built="$target/wasm32-unknown-unknown/release/fielddeck_chains.wasm"
if [[ "${1:-}" == "--check" ]]; then
  cmp -s "$built" "$out" && echo "committed module matches the Rust source" \
    || { echo "committed module is stale: run npm run build:wasm" >&2; exit 1; }
else
  cp "$built" "$out"
  echo "wrote $out ($(wc -c <"$out") bytes)"
fi
