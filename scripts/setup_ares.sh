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
BIN_DIR="${HERMES_ARES_BIN_DIR:-$DEFAULT_ARES_HOME/bin}"
GIT_DEPTH="${HERMES_ARES_GIT_DEPTH:-1}"
CLIENT="demo-wholesaler"
BUSINESS_NAME="Demo Wholesale"
OWNER_NAME="Owner"
LANGUAGE="english_hinglish"
TIMEZONE="Asia/Kolkata"
USE_CURRENT_REPO=0
SKIP_GATEWAY_HINT=0
INSTALL_WRAPPERS=1
AUTO_INSTALL_UV=1

log() { printf '[ares-setup] %s\n' "$*"; }
fail() { printf '[ares-setup] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Reliable one-command setup for Ares Wholesale AIOS.

It works even when Hermes is not installed globally. The script clones Ares,
installs/runs its local Hermes environment with uv, creates the client profile,
runs a smoke test, and installs small wrapper commands:

  ares         -> runs: uv run hermes ares ... inside the Ares checkout
  ares-hermes  -> runs: uv run hermes ... inside the Ares checkout

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
  --bin-dir PATH            Wrapper command directory (default: ~/.ares/bin)
  --git-depth N             Clone depth, use 0 for full clone (default: 1)
  --current-repo            Use the current working tree instead of cloning
  --no-wrapper              Do not install ares / ares-hermes wrapper commands
  --no-install-uv           Fail instead of installing uv automatically
  --skip-gateway-hint       Do not print gateway next steps
  -h, --help                Show this help

Examples:
  curl -fsSL https://raw.githubusercontent.com/raghavbadhwar/ares-wholesale-aios/main/scripts/setup_ares.sh | bash -s -- \\
    --client gupta-distributors \\
    --business-name "Gupta Distributors" \\
    --owner-name "Mr Gupta"

  ares autonomous-cycle --client gupta-distributors
  ares mobile-approvals --client gupta-distributors
  ares-hermes gateway setup
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
    --bin-dir) BIN_DIR="${2:-}"; shift 2 ;;
    --git-depth) GIT_DEPTH="${2:-}"; shift 2 ;;
    --current-repo) USE_CURRENT_REPO=1; shift ;;
    --no-wrapper) INSTALL_WRAPPERS=0; shift ;;
    --no-install-uv) AUTO_INSTALL_UV=0; shift ;;
    --skip-gateway-hint) SKIP_GATEWAY_HINT=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

[[ -n "$CLIENT" ]] || fail "--client cannot be empty"
[[ -n "$BUSINESS_NAME" ]] || fail "--business-name cannot be empty"
[[ -n "$OWNER_NAME" ]] || fail "--owner-name cannot be empty"
[[ -n "$ARES_HOME_VALUE" ]] || fail "--ares-home cannot be empty"
[[ -n "$INSTALL_DIR" ]] || fail "--install-dir cannot be empty"
[[ -n "$BIN_DIR" ]] || fail "--bin-dir cannot be empty"

ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  fail "git is required. On macOS, run: xcode-select --install"
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    UV_BIN=$(command -v uv)
    export UV_BIN
    return 0
  fi

  [[ "$AUTO_INSTALL_UV" -eq 1 ]] || fail "uv is required. Install it from https://docs.astral.sh/uv/"
  command -v curl >/dev/null 2>&1 || fail "curl is required to auto-install uv"

  log "uv not found; installing uv locally"
  curl -LsSf https://astral.sh/uv/install.sh | sh

  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    fail "uv install finished but uv is not on PATH. Add ~/.local/bin to PATH and rerun."
  fi
  UV_BIN=$(command -v uv)
  export UV_BIN
}

clone_or_update_repo() {
  if [[ "$USE_CURRENT_REPO" -eq 1 ]]; then
    REPO_DIR=$(pwd)
    [[ -f "$REPO_DIR/pyproject.toml" ]] || fail "--current-repo must be run from the Ares repo root"
    export REPO_DIR
    return 0
  fi

  REPO_DIR="$INSTALL_DIR"
  export REPO_DIR

  if [[ -d "$REPO_DIR/.git" ]]; then
    log "Updating existing Ares checkout at $REPO_DIR"
    git -C "$REPO_DIR" fetch origin "$BRANCH"
    git -C "$REPO_DIR" checkout "$BRANCH"
    git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
  else
    log "Cloning Ares from $REPO_URL#$BRANCH into $REPO_DIR"
    mkdir -p "$(dirname "$REPO_DIR")"
    if [[ "$GIT_DEPTH" == "0" ]]; then
      git clone --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
    else
      git clone --depth "$GIT_DEPTH" --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
    fi
  fi
}

run_ares() {
  (
    cd "$REPO_DIR"
    ARES_HOME="$ARES_HOME" "$UV_BIN" run hermes ares "$@"
  )
}

install_wrappers() {
  [[ "$INSTALL_WRAPPERS" -eq 1 ]] || return 0

  mkdir -p "$BIN_DIR"

  cat > "$BIN_DIR/ares" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export ARES_HOME="\${ARES_HOME:-$ARES_HOME}"
cd "$REPO_DIR"
exec "$UV_BIN" run hermes ares "\$@"
EOF

  cat > "$BIN_DIR/ares-hermes" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export ARES_HOME="\${ARES_HOME:-$ARES_HOME}"
cd "$REPO_DIR"
exec "$UV_BIN" run hermes "\$@"
EOF

  chmod +x "$BIN_DIR/ares" "$BIN_DIR/ares-hermes"
}

path_hint() {
  case ":$PATH:" in
    *":$BIN_DIR:"*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_git
ensure_uv
clone_or_update_repo

export ARES_HOME="$ARES_HOME_VALUE"
mkdir -p "$ARES_HOME"

log "Verifying local Ares Hermes command"
run_ares --help >/dev/null

log "Creating/updating Ares client profile: $CLIENT"
run_ares setup \
  --client "$CLIENT" \
  --business-name "$BUSINESS_NAME" \
  --owner-name "$OWNER_NAME" \
  --language "$LANGUAGE" \
  --timezone "$TIMEZONE" \
  --ares-home "$ARES_HOME"

log "Running first autonomous cycle smoke test"
run_ares autonomous-cycle --client "$CLIENT" >/dev/null

install_wrappers

cat <<EOF

Ares is ready.

Repo:
  $REPO_DIR

Ares home:
  $ARES_HOME
EOF

if [[ "$INSTALL_WRAPPERS" -eq 1 ]]; then
  cat <<EOF

Wrapper commands installed:
  $BIN_DIR/ares
  $BIN_DIR/ares-hermes
EOF
  if ! path_hint; then
    cat <<EOF

Add this to your shell PATH to run 'ares' from anywhere:
  export PATH="$BIN_DIR:\$PATH"

For zsh on macOS, run once:
  echo 'export PATH="$BIN_DIR:\$PATH"' >> ~/.zshrc
  source ~/.zshrc
EOF
  fi
  cat <<EOF

Daily commands:
  ares autonomous-cycle --client $CLIENT
  ares mobile-approvals --client $CLIENT
  ares mobile-reply --client $CLIENT --reply "haan appr_xxx"

Cron specs:
  ares print-cron-specs --client $CLIENT
EOF
else
  cat <<EOF

Daily commands:
  cd $REPO_DIR
  export ARES_HOME=$ARES_HOME
  uv run hermes ares autonomous-cycle --client $CLIENT
  uv run hermes ares mobile-approvals --client $CLIENT
  uv run hermes ares mobile-reply --client $CLIENT --reply "haan appr_xxx"

Cron specs:
  uv run hermes ares print-cron-specs --client $CLIENT
EOF
fi

if [[ "$SKIP_GATEWAY_HINT" -eq 0 ]]; then
  if [[ "$INSTALL_WRAPPERS" -eq 1 ]]; then
    cat <<EOF

Gateway next:
  ares-hermes gateway setup
  ares-hermes gateway run
EOF
  else
    cat <<EOF

Gateway next:
  cd $REPO_DIR
  uv run hermes gateway setup
  uv run hermes gateway run
EOF
  fi
  cat <<EOF

Gateway slash command after restart:
  /ares $CLIENT cycle
  /ares $CLIENT approvals
  /ares $CLIENT reply haan appr_xxx
EOF
fi
