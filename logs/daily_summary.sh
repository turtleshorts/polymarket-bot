#!/bin/bash
# Psyco Capital — Daily Bot Summary
# Run manually:  bash logs/daily_summary.sh
# Auto output:   logs/daily_summary.txt (written every 24h by launchd)

BOT_DIR="/Users/elysmith/polymarket-trader"
LOG="$BOT_DIR/logs/bot.log"
TRADES="$BOT_DIR/logs/trades.jsonl"
COSTS="$BOT_DIR/logs/api_costs.jsonl"
TODAY=$(date +%Y-%m-%d)
PYTHON="$BOT_DIR/venv/bin/python"

echo "======================================================"
echo "  PSYCO CAPITAL — DAILY BOT SUMMARY"
echo "  Date: $TODAY  |  Generated: $(date '+%H:%M %Z')"
echo "======================================================"

# ── Bot daemon status ──────────────────────────────────────
echo ""
echo "BOT STATUS:"
STATUS=$(launchctl list | awk '$3 == "com.psyco.polytrader"')
if [ -n "$STATUS" ]; then
    PID=$(echo "$STATUS" | awk '{print $1}')
    EXIT=$(echo "$STATUS" | awk '{print $2}')
    if [ "$PID" != "-" ] && [ "$PID" != "0" ]; then
        echo "  Running  (PID $PID)"
    else
        echo "  Stopped  (last exit code: $EXIT)"
    fi
else
    echo "  Not registered with launchd"
fi

# ── Markets scanned ────────────────────────────────────────
echo ""
echo "MARKETS SCANNED TODAY:"
CYCLES=$(grep "Cycle start" "$LOG" 2>/dev/null | grep "$TODAY" | wc -l | tr -d ' ')
FLAGGED=$(grep "markets flagged" "$LOG" 2>/dev/null | grep "$TODAY" | grep -oE '[0-9]+ markets flagged' | awk '{sum+=$1} END {print sum+0}')
echo "  Cycles completed: $CYCLES"
echo "  Total flagged for research: $FLAGGED"

# ── Paper trades placed ────────────────────────────────────
echo ""
echo "PAPER TRADES TODAY (mode=dry):"
if [ -f "$TRADES" ]; then
    $PYTHON - <<PYEOF
import json, sys
from pathlib import Path

trades_path = Path("$TRADES")
today = "$TODAY"
trades = []
with open(trades_path) as f:
    for line in f:
        try:
            t = json.loads(line)
            if t.get("timestamp", "")[:10] == today and t.get("mode") == "dry":
                trades.append(t)
        except:
            pass

if not trades:
    print("  No paper trades placed today")
else:
    print(f"  Trades placed: {len(trades)}")
    for t in trades:
        print(f"    [{t['direction']}] {t['question'][:55]}")
        print(f"         \${t['bet_usd']:.2f} @ {t['entry_price']:.0%} | edge={t.get('edge',0):.2%} conf={t.get('confidence',0):.0%}")
PYEOF
else
    echo "  No trades file yet"
fi

# ── Simulated P&L ──────────────────────────────────────────
echo ""
echo "SIMULATED P&L (all-time, paper trades):"
if [ -f "$TRADES" ]; then
    $PYTHON - <<PYEOF
import json
from pathlib import Path

trades = []
with open("$TRADES") as f:
    for line in f:
        try: trades.append(json.loads(line))
        except: pass

dry = [t for t in trades if t.get("mode") == "dry"]
settled = [t for t in dry if t.get("status") in ("win", "loss")]
open_t  = [t for t in dry if t.get("status") == "open"]

wins   = sum(1 for t in settled if t["status"] == "win")
losses = sum(1 for t in settled if t["status"] == "loss")

def pnl(t):
    if t["status"] == "win":
        return t["bet_usd"] * (1 - t["entry_price"]) / t["entry_price"]
    return -t["bet_usd"]

net = sum(pnl(t) for t in settled)
wagered = sum(t["bet_usd"] for t in settled)
open_exp = sum(t["bet_usd"] for t in open_t)

print(f"  Settled: {len(settled)}  ({wins}W / {losses}L)  |  Open: {len(open_t)}")
print(f"  Total wagered:    \${wagered:.2f}")
print(f"  Net P&L:          \${net:+.2f}")
print(f"  Open exposure:    \${open_exp:.2f}")
if settled:
    wr = wins / len(settled)
    print(f"  Win rate:         {wr:.0%}  {'✓ on target' if wr >= 0.60 else '⚠ below 60% target'}")
else:
    print("  No settled trades yet — bot is still in early scanning phase")
PYEOF
else
    echo "  No trades file yet"
fi

# ── API costs ──────────────────────────────────────────────
echo ""
echo "API COSTS:"
if [ -f "$COSTS" ]; then
    $PYTHON - <<PYEOF
import json
from datetime import date
from pathlib import Path

today = "$TODAY"
all_cost = 0.0
today_cost = 0.0
with open("$COSTS") as f:
    for line in f:
        try:
            e = json.loads(line)
            all_cost += float(e.get("cost_usd", 0))
            if e.get("date") == today:
                today_cost += float(e.get("cost_usd", 0))
        except:
            pass
print(f"  Today:     \${today_cost:.4f}  (daily limit \$50.00)")
print(f"  All-time:  \${all_cost:.4f}")
PYEOF
else
    echo "  No API cost data yet"
fi

# ── Errors ─────────────────────────────────────────────────
echo ""
echo "ERRORS TODAY:"
ERRORS=$(grep "\[ERROR\]" "$LOG" 2>/dev/null | grep "$TODAY")
if [ -n "$ERRORS" ]; then
    echo "$ERRORS" | tail -10 | sed 's/^/  /'
else
    echo "  No errors today"
fi

# ── Last log lines ─────────────────────────────────────────
echo ""
echo "LAST 5 LOG LINES:"
tail -5 "$LOG" 2>/dev/null | sed 's/^/  /' || echo "  Log not found"

echo ""
echo "======================================================"
