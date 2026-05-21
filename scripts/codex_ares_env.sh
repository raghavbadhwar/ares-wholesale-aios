#!/usr/bin/env bash
set -euo pipefail

export ARES_REPO="/Users/raghav/.ares/ares"
export UV_CACHE_DIR="/private/tmp/ares-uv-cache"
export CODEX_SANDBOX_MODE="workspace-write"
export CODEX_COMMON_ARGS="-C $ARES_REPO -s $CODEX_SANDBOX_MODE"

mkdir -p "$UV_CACHE_DIR"
cd "$ARES_REPO"

printf 'ARES_REPO=%s\n' "$ARES_REPO"
printf 'branch=%s\n' "$(git branch --show-current 2>/dev/null || true)"
printf 'uv_cache=%s\n' "$UV_CACHE_DIR"
printf 'codex=%s\n' "$(command -v codex)"
printf 'uv=%s\n' "$(command -v uv)"
