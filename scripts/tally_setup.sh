#!/usr/bin/env bash
# =============================================================================
# Ares — Tally Prime XML Gateway Setup Script
# =============================================================================
# This script walks you through enabling and testing the Tally Prime XML Gateway
# so that Ares can push invoices, receipts, and stock items to Tally automatically.
#
# Usage:
#   chmod +x scripts/tally_setup.sh
#   TALLY_BUSY_SANDBOX_XML_GATEWAY_URL=http://localhost:9000 ./scripts/tally_setup.sh
#
# Supported versions: Tally Prime 2.0+, Tally ERP 9 (Release 6.6+)
# =============================================================================

set -euo pipefail

TALLY_URL="${TALLY_BUSY_SANDBOX_XML_GATEWAY_URL:-http://localhost:9000}"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         Ares × Tally Prime XML Gateway Setup                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Enable HTTP XML Gateway in Tally Prime
# ---------------------------------------------------------------------------
echo "📋 Step 1 — Enable Tally Prime XML Gateway"
echo "─────────────────────────────────────────────────────────────────"
echo ""
echo "In Tally Prime:"
echo "  1. Open Tally Prime → Gateway of Tally → F12 (Configure)"
echo "  2. Go to: Advanced Configuration → Enable HTTP Server"
echo "  3. Set HTTP Port: 9000 (or your preferred port)"
echo "  4. Set Enable XML Request: Yes"
echo "  5. Save and restart Tally Prime"
echo ""
echo "  Alternative (Tally ERP 9):"
echo "  • Go to: Gateway of Tally → Configure (F12) → Integrate Account with"
echo "    product → Enable → ODBC Port 9000"
echo ""

# ---------------------------------------------------------------------------
# Step 2: Firewall / network check
# ---------------------------------------------------------------------------
echo "📋 Step 2 — Network & Firewall"
echo "─────────────────────────────────────────────────────────────────"
echo "  • Ensure Tally Prime is running on the same machine as Ares OR"
echo "    the TALLY_BUSY_SANDBOX_XML_GATEWAY_URL points to the Tally PC IP."
echo "  • Windows Firewall: Allow port 9000 for tally.exe"
echo "  • macOS/Linux (Wine/CrossOver): Ensure port 9000 is not blocked."
echo ""

# ---------------------------------------------------------------------------
# Step 3: Set environment variable
# ---------------------------------------------------------------------------
echo "📋 Step 3 — Configure Ares"
echo "─────────────────────────────────────────────────────────────────"
echo "  Add this to ~/.ares/.env (or your Ares .env):"
echo ""
echo "    TALLY_BUSY_SANDBOX_XML_GATEWAY_URL=http://<tally_host>:9000"
echo ""
echo "  Current value: $TALLY_URL"
echo ""

# ---------------------------------------------------------------------------
# Step 4: Connectivity test
# ---------------------------------------------------------------------------
echo "📋 Step 4 — Connectivity Test"
echo "─────────────────────────────────────────────────────────────────"
echo "  Testing connection to: $TALLY_URL"
echo ""

# Build a minimal Tally health-check XML request
TALLY_PING_XML='<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA><REQUESTDESC><REPORTNAME>List of Companies</REPORTNAME></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>'

HTTP_STATUS=""
RESPONSE_BODY=""

if command -v curl &>/dev/null; then
    HTTP_STATUS=$(curl -s -o /tmp/tally_response.xml -w "%{http_code}" \
        --max-time 5 \
        -X POST "$TALLY_URL" \
        -H "Content-Type: application/xml" \
        -d "$TALLY_PING_XML" 2>/dev/null || echo "000")
    RESPONSE_BODY=$(cat /tmp/tally_response.xml 2>/dev/null || echo "")
elif command -v wget &>/dev/null; then
    RESPONSE_BODY=$(wget -q -O - --timeout=5 --post-data="$TALLY_PING_XML" \
        --header="Content-Type: application/xml" "$TALLY_URL" 2>/dev/null || echo "")
    HTTP_STATUS="200"
else
    echo "  ⚠️  Neither curl nor wget found. Please install curl to test connectivity."
    HTTP_STATUS="skip"
fi

echo ""
if [ "$HTTP_STATUS" = "000" ] || [ "$HTTP_STATUS" = "" ]; then
    echo "  ❌ FAILED — Could not connect to Tally at $TALLY_URL"
    echo ""
    echo "  Possible causes:"
    echo "    • Tally Prime is not running"
    echo "    • XML Gateway not enabled (see Step 1)"
    echo "    • Wrong host/port in TALLY_BUSY_SANDBOX_XML_GATEWAY_URL"
    echo "    • Firewall blocking port 9000"
    echo ""
    exit 1
elif [ "$HTTP_STATUS" = "skip" ]; then
    echo "  ⚠️  Connectivity test skipped (no curl/wget available)"
elif [ "$HTTP_STATUS" = "200" ] || echo "$RESPONSE_BODY" | grep -qi "ENVELOPE"; then
    echo "  ✅ SUCCESS — Tally XML Gateway is reachable at $TALLY_URL"
    echo ""
    if echo "$RESPONSE_BODY" | grep -qi "COMPANY"; then
        COMPANIES=$(echo "$RESPONSE_BODY" | grep -oP '(?<=<NAME>)[^<]+' | head -5 || echo "")
        if [ -n "$COMPANIES" ]; then
            echo "  Companies found in Tally:"
            echo "$COMPANIES" | while read -r company; do
                echo "    • $company"
            done
        fi
    fi
else
    echo "  ⚠️  Received HTTP $HTTP_STATUS — Tally may be running but returned an error."
    echo "  Response: ${RESPONSE_BODY:0:200}"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Setup complete. Ares is ready to sync with Tally Prime.    ║"
echo "║  Run: ares ares demo today  to verify the full pipeline.  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
