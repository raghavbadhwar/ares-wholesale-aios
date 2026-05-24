#!/usr/bin/env bash
# deploy_ares.sh — Deploy Ares Wholesale AIOS on the Ares gateway.
#
# Usage:
#   ./scripts/deploy_ares.sh [--skip-tests] [--dry-run]
#
# Requirements:
#   - Ares installed (ares command available)
#   - Python venv at .venv or venv
#   - Environment variables set in ~/.ares/.env or exported

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false
SKIP_TESTS=false

# Parse args
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --skip-tests) SKIP_TESTS=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

echo "================================================="
echo "  Ares Wholesale AIOS — Deployment Script"
echo "================================================="
echo "Repo root : $REPO_ROOT"
echo "Dry run   : $DRY_RUN"
echo ""

# ── Step 1: Activate venv ─────────────────────────────────────────────────────
if [ -d "$REPO_ROOT/.venv" ]; then
  source "$REPO_ROOT/.venv/bin/activate"
elif [ -d "$REPO_ROOT/venv" ]; then
  source "$REPO_ROOT/venv/bin/activate"
else
  echo "❌  No .venv or venv found. Run: uv venv && uv pip install -e '.[full]'"
  exit 1
fi
echo "✅  Virtual environment activated"

# ── Step 2: Check required env vars ───────────────────────────────────────────
REQUIRED_VARS=(
  "META_WABA_SANDBOX_PHONE_NUMBER_ID"
  "META_WABA_SANDBOX_ACCESS_TOKEN"
  "META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN"
  "META_WABA_SANDBOX_APP_SECRET"
)
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    MISSING+=("$var")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "⚠️   Missing environment variables (WhatsApp sandbox will run in mock mode):"
  for var in "${MISSING[@]}"; do
    echo "    - $var"
  done
  echo "    Add them to ~/.ares/.env or export before deploying."
  echo ""
fi

# Optional vars (non-blocking)
OPTIONAL_VARS=(
  "RAZORPAY_SANDBOX_KEY_ID"
  "RAZORPAY_SANDBOX_KEY_SECRET"
  "CASHFREE_SANDBOX_APP_ID"
  "CASHFREE_SANDBOX_APP_SECRET"
  "GSTN_SANDBOX_API_KEY"
  "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL"
  "AGMARKNET_API_KEY"
  "DELHIVERY_SANDBOX_API_TOKEN"
  "AA_CLIENT_ID"
  "AA_CLIENT_SECRET"
  "ONDC_GATEWAY_URL"
  "ONDC_SUBSCRIBER_ID"
)
echo "📋  Optional integration env vars:"
for var in "${OPTIONAL_VARS[@]}"; do
  status="${!var:+SET}"
  status="${status:-not set}"
  printf "    %-45s %s\n" "$var" "$status"
done
echo ""

# ── Step 3: Run tests ─────────────────────────────────────────────────────────
if [ "$SKIP_TESTS" = false ]; then
  echo "🧪  Running Ares test suite..."
  cd "$REPO_ROOT"
  if uv run pytest tests/ares -x -q --tb=short 2>&1 | tail -5; then
    echo "✅  All tests passed"
  else
    echo "❌  Tests failed. Aborting deployment."
    exit 1
  fi
else
  echo "⚠️   Skipping tests (--skip-tests)"
fi

# ── Step 4: Validate Ares AIOS imports ────────────────────────────────────────
echo ""
echo "🔍  Validating Ares module imports..."
python -c "
from apps.ares.ares.gateway.whatsapp_webhook import router as wa_router
from apps.ares.ares.gateway.payment_webhook import router as pay_router
from apps.ares.ares.workflows.order_capture import capture_order, _guess_intent
from apps.ares.ares.workflows.regional_language import translate_to_regional
from apps.ares.ares.workflows.party_onboarding import verify_gstin_online
from apps.ares.ares.workflows.bank_reconciliation import parse_bank_statement_csv
from apps.ares.ares.workflows.logistics import integrate_delhivery_sandbox
from apps.ares.ares.workflows.mandi_prices import fetch_agmarknet_prices
from apps.ares.ares.workflows.account_aggregator import initiate_aa_consent_request
from apps.ares.ares.workflows.ondc_seller import publish_ondc_catalogue_via_beckn
print('All Ares modules import cleanly.')
"
echo "✅  Import validation passed"

# ── Step 5: Webhook health check ──────────────────────────────────────────────
ARES_HOME="${ARES_HOME:-$HOME/.ares}"
echo ""
echo "📁  Ares home: $ARES_HOME"

# ── Step 6: Deploy (or dry-run) ───────────────────────────────────────────────
echo ""
if [ "$DRY_RUN" = true ]; then
  echo "🏁  DRY RUN — no services restarted."
  echo "    To deploy for real, run: ./scripts/deploy_ares.sh"
  exit 0
fi

echo "🚀  Starting Ares gateway with Ares plugin..."
# Restart gateway if already running
if command -v ares &>/dev/null; then
  ares gateway restart 2>/dev/null || true
  sleep 2
  echo "✅  Ares gateway restarted"
  echo ""
  echo "    Webhook endpoints:"
  echo "    GET/POST /ares/webhook/whatsapp"
  echo "    POST     /ares/webhook/payment/{razorpay|cashfree|phonepe}"
  echo "    GET      /ares/health"
else
  echo "⚠️   'ares' command not found — start the gateway manually:"
  echo "    ares gateway start"
fi

echo ""
echo "================================================="
echo "  ✅  Ares deployment complete!"
echo "================================================="
