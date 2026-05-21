#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/raghav/.ares/ares"
DEFAULT_PROMPT="$ROOT/docs/ares/benchmark/CODEX_MASTER_PROMPT.md"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  ./scripts/start_codex_ares.sh [prompt-file]

Examples:
  ./scripts/start_codex_ares.sh
  ./scripts/start_codex_ares.sh docs/ares/benchmark/CODEX_GSTR1_PROMPT.md
EOF
  exit 0
fi

PROMPT_FILE="${1:-$DEFAULT_PROMPT}"

source "$ROOT/scripts/codex_ares_env.sh" >/dev/null
cd "$ROOT"

printf '\n== Ares Codex Session ==\n'
printf 'repo: %s\n' "$ROOT"
printf 'branch: %s\n' "$(git branch --show-current)"
printf 'prompt: %s\n\n' "$PROMPT_FILE"

exec codex exec -C "$ROOT" -s workspace-write - < "$PROMPT_FILE"
