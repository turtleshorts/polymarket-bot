#!/bin/bash
# ============================================================
# Polymarket Trading Bot — Mac Mini Setup Script
# Run this once to set up the full environment.
# Usage: chmod +x setup.sh && ./setup.sh
# ============================================================

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="$SCRIPT_DIR"
USERNAME=$(whoami)

echo "======================================"
echo " Polymarket Bot Setup"
echo " Directory: $BOT_DIR"
echo " User: $USERNAME"
echo "======================================"
echo ""

# 1. Check Python
echo "→ Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 not found. Install from python.org or via Homebrew:"
    echo "  brew install python3"
    exit 1
fi
PYTHON_VER=$(python3 --version)
echo "  Found: $PYTHON_VER"

# 2. Create virtual environment
echo ""
echo "→ Creating Python virtual environment..."
python3 -m venv "$BOT_DIR/venv"
source "$BOT_DIR/venv/bin/activate"
echo "  Virtual env created at $BOT_DIR/venv"

# 3. Install dependencies
echo ""
echo "→ Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install \
    anthropic \
    requests \
    python-dotenv \
    --quiet
echo "  Dependencies installed."

# 4. Create .env file if missing
if [ ! -f "$BOT_DIR/.env" ]; then
    echo ""
    echo "→ Creating .env template..."
    cat > "$BOT_DIR/.env" << 'EOF'
# Polymarket Trading Bot — Environment Secrets
# DO NOT commit this file to git

# Anthropic API key (for calibration and post-mortem agents)
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# Polymarket wallet (Polygon network)
POLYGON_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
POLYGON_ADDRESS=0xYOUR_WALLET_ADDRESS_HERE

# Polymarket CLOB API key (get from polymarket.com/settings)
POLYMARKET_API_KEY=YOUR_POLYMARKET_API_KEY_HERE

# CryptoPanic API key (optional — public feed works without it)
# Get free key at cryptopanic.com
CRYPTOPANIC_API_KEY=
EOF
    echo "  Created .env template at $BOT_DIR/.env"
    echo "  ⚠️  EDIT THIS FILE with your actual keys before running."
else
    echo "  .env already exists, skipping."
fi

# 5. Create logs directory
echo ""
echo "→ Creating logs directory..."
mkdir -p "$BOT_DIR/logs"
touch "$BOT_DIR/logs/trades.jsonl"
touch "$BOT_DIR/logs/learnings.jsonl"
echo "  Logs directory ready."

# 6. Install launchd plist for 24/7 operation
echo ""
echo "→ Setting up macOS launch agent..."
PLIST_SRC="$BOT_DIR/assets/com.psyco.polytrader.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.psyco.polytrader.plist"
PYTHON_PATH="$BOT_DIR/venv/bin/python"

# Substitute actual paths into plist
sed \
    -e "s|/Users/YOUR_USERNAME|$HOME|g" \
    -e "s|/Users/YOUR_USERNAME/polymarket-trader/venv/bin/python|$PYTHON_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DST"

echo "  Plist installed to $PLIST_DST"

# 7. Verify plist syntax
if plutil -lint "$PLIST_DST" &>/dev/null; then
    echo "  Plist syntax: ✅ valid"
else
    echo "  Plist syntax: ❌ invalid — check $PLIST_DST"
fi

# 8. Test dry run
echo ""
echo "→ Running quick dry-run test (one cycle)..."
source "$BOT_DIR/venv/bin/activate"
cd "$BOT_DIR"

# Load .env for test
if [ -f "$BOT_DIR/.env" ]; then
    export $(grep -v '^#' "$BOT_DIR/.env" | xargs) 2>/dev/null || true
fi

python scripts/run_bot.py --mode dry --once && echo "  Dry run: ✅ completed" || echo "  Dry run: ⚠️  completed with errors (check logs)"

echo ""
echo "======================================"
echo " Setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit your secrets:"
echo "   nano $BOT_DIR/.env"
echo ""
echo "2. Fund your Polymarket wallet with USDC on Polygon"
echo "   Min recommended: \$500 USDC"
echo ""
echo "3. Update bankroll in config.json:"
echo "   nano $BOT_DIR/config.json"
echo "   → Set risk.bankroll_usd to your actual USDC balance"
echo ""
echo "4. Install the Polymarket MCP server:"
echo "   git clone https://github.com/caiovicentino/polymarket-mcp-server.git"
echo "   Then add to ~/.claude.json"
echo ""
echo "5. Start bot (dry run mode for 48h first):"
echo "   launchctl load ~/Library/LaunchAgents/com.psyco.polytrader.plist"
echo ""
echo "6. Watch logs:"
echo "   tail -f $BOT_DIR/logs/bot.log"
echo ""
echo "7. After 48h, check trades:"
echo "   python $BOT_DIR/scripts/review.py --today"
echo "   Then switch config to live mode."
echo ""
echo "⚠️  IMPORTANT: The bot runs in dry mode for the first 48 hours"
echo "   regardless of mode flag. This is a safety feature."
echo ""
