#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/raghav/.ares/ares"
source "$ROOT/scripts/codex_ares_env.sh" >/dev/null
cd "$ROOT"

exec codex resume --last --include-non-interactive --no-alt-screen
