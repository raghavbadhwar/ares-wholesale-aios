#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME=$(basename "$0")
DEFAULT_REPO_URL="https://github.com/raghavbadhwar/ares-wholesale-aios.git"
DEFAULT_BRANCH="main"
DEFAULT_INSTALL_DIR="$HOME/.ares/ares"
DEFAULT_ARES_HOME="$HOME/.ares"

REPO_URL="${HERMES_ARES_REPO_URL:-$DEFAULT_REPO_URL}"
BRANCH="${HERMES_ARES_BRANCH:-$DEFAULT_BRANCH}"
INSTALL_DIR="${HERMES_ARES_INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
ARES_HOME_VALUE="${ARES_HOME:-$DEFAULT_ARES_HOME}"
CLIENT="demo-wholesaler"
BUSINESS_NAME="Demo Wholesale"
OWNER_NAME="Owner"
LANGUAGE="english_hinglish"
TIMEZONE="Asia/Kolkata"
USE_CURRENT_REPO=0
SKIP_GATEWAY_HINT=0

log() { printf '[ares-setup] %s\n' "$*"; }
fail() { printf '[ares-setup] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Seamless local setup for Ares Wholesale AIOS on top of Hermes.

Options:
  --client SLUG             Client slug (default: demo-wholesaler)
  --business-name NAME      Business name (default: Demo Wholesale)
  --owner-name NAME         Owner name (default: Owner)
  --language VALUE          Language preference (default: english_hinglish)
  --timezone TZ             Timezone (default: Asia/Kolkata)
  --ares-home PATH          Ares data directory (default: ~/.ares or ARES_HOME)
  --repo-url URL            Git repo URL (default: $DEFAULT_REPO_URL)
  --branch NAME             Git branch to use (default: $DEFAULT_BRANCH)
  --install-dir PATH        Clone/update location (default: ~/.ares/ares)
  --current-repo            Use the current working tree instead of cloning
  --skip-gateway-hint       Do not print gateway next steps
  -h, --help                Show this help

Examples:
  curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \\
    --client gupta-distributors \\
    --business-name "Gupta Distributors" \\
    --owner-name "Mr Gupta"

  ./scripts/setup_ares.sh --current-repo --client demo --business-name Demo --owner-name Raghav
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client) CLIENT="${2:-}"; shift 2 ;;
    --business-name) BUSINESS_NAME="${2:-}"; shift 2 ;;
    --owner-name) OWNER_NAME="${2:-}"; shift 2 ;;
    --language) LANGUAGE="${2:-}"; shift 2 ;;
    --timezone) TIMEZONE="${2:-}"; shift 2 ;;
    --ares-home) ARES_HOME_VALUE="${2:-}"; shift 2 ;;
    --repo-url) REPO_URL="${2:-}"; shift 2 ;;
    --branch) BRANCH="${2:-}"; shift 2 ;;
    --install-dir) INSTALL_DIR="${2:-}"; shift 2 ;;
    --current-repo) USE_CURRENT_REPO=1; shift ;;
    --skip-gateway-hint) SKIP_GATEWAY_HINT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

[[ -n "$CLIENT" ]] || fail "--client cannot be empty"
[[ -n "$BUSINESS_NAME" ]] || fail "--business-name cannot be empty"
[[ -n "$OWNER_NAME" ]] || fail "--owner-name cannot be empty"

command -v git >/dev/null 2>&1 || fail "git is required"
command -v uv >/dev/null 2>&1 || fail "uv is required. Install it from https://docs.astral.sh/uv/"

if [[ "$USE_CURRENT_REPO" -eq 1 ]]; then
  REPO_DIR=$(pwd)
  [[ -f "$REPO_DIR/pyproject.toml" ]] || fail "--current-repo must be run from the Ares repo root"
else
  REPO_DIR="$INSTALL_DIR"
  if [[ -d "$REPO_DIR/.git" ]]; then
    log "Updating existing Ares checkout at $REPO_DIR"
    git -C "$REPO_DIR" fetch origin "$BRANCH"
    git -C "$REPO_DIR" checkout "$BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
  else
    log "Cloning Ares from $REPO_URL#$BRANCH into $REPO_DIR"
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
  fi
fi

export ARES_HOME="$ARES_HOME_VALUE"
mkdir -p "$ARES_HOME"

log "Verifying Ares Hermes plugin"
(
  cd "$REPO_DIR"
  uv run hermes ares --help >/dev/null
)

log "Creating/updating Ares client profile: $CLIENT"
(
  cd "$REPO_DIR"
  uv run hermes ares setup \
    --client "$CLIENT" \
    --business-name "$BUSINESS_NAME" \
    --owner-name "$OWNER_NAME" \
    --language "$LANGUAGE" \
    --timezone "$TIMEZONE" \
    --ares-home "$ARES_HOME"
)

log "Running first autonomous cycle smoke test"
(
  cd "$REPO_DIR"
  uv run hermes ares autonomous-cycle --client "$CLIENT" >/dev/null
)

cat <<EOF

Ares is ready.

Repo:
  $REPO_DIR

Ares home:
  $ARES_HOME

Daily commands:
  cd $REPO_DIR
  export ARES_HOME=$ARES_HOME
  uv run hermes ares autonomous-cycle --client $CLIENT
  uv run hermes ares mobile-approvals --client $CLIENT
  uv run hermes ares mobile-reply --client $CLIENT --reply "haan appr_xxx"

Cron specs:
  uv run hermes ares print-cron-specs --client $CLIENT
EOF

if [[ "$SKIP_GATEWAY_HINT" -eq 0 ]]; then
  cat <<EOF

Gateway next:
  cd $REPO_DIR
  hermes gateway setup
  hermes gateway run

Gateway slash command after restart:
  /ares $CLIENT cycle
  /ares $CLIENT approvals
  /ares $CLIENT reply haan appr_xxx
EOF
fi
