#!/usr/bin/env python3
"""
metrics.py — Performance Tracking
Calculates and displays: Win Rate, Sharpe Ratio, Brier Score, Profit Factor, Max Drawdown.
Run this anytime to see how the bot is performing.

Usage:
  python scripts/metrics.py
  python scripts/metrics.py --full   # include per-trade breakdown
"""

import json
import math
import argparse
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRADES_PATH = ROOT / "logs" / "trades.jsonl"
LEARNINGS_PATH = ROOT / "logs" / "learnings.jsonl"
API_COSTS_PATH = ROOT / "logs" / "api_costs.jsonl"


def load_trades():
    if not TRADES_PATH.exists():
        return []
    trades = []
    with open(TRADES_PATH) as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except Exception:
                pass
    return trades


def estimate_pnl(trade):
    """Estimate P&L for a settled trade. Simplified (full version needs exit price)."""
    if trade["status"] == "win":
        # Win: collected (1 - entry_price) per dollar bet
        return round(trade["bet_usd"] * (1 - trade["entry_price"]) / trade["entry_price"], 2)
    elif trade["status"] == "loss":
        return -trade["bet_usd"]
    return 0.0


def calculate_sharpe(returns):
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return round(mean_r / std_r, 3)


def calculate_brier_score(settled_trades):
    """
    Brier Score uses the bot's true_prob_estimate vs actual outcome.
    Lower = better calibrated. Target < 0.25.
    """
    if not settled_trades:
        return None
    items = []
    for t in settled_trades:
        predicted = t.get("true_prob_estimate")
        if predicted is None:
            continue
        outcome = 1 if t["status"] == "win" else 0
        # Adjust for direction: if we bet NO, invert
        if t.get("direction") == "NO":
            predicted = 1 - predicted
            outcome = 1 - outcome
        items.append((predicted, outcome))

    if not items:
        return None
    bs = sum((p - o) ** 2 for p, o in items) / len(items)
    return round(bs, 4)


def calculate_max_drawdown(pnl_series):
    if not pnl_series:
        return 0.0
    peak = pnl_series[0]
    max_dd = 0.0
    for v in pnl_series:
        if v > peak:
            peak = v
        dd = (peak - v)
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def get_total_api_cost():
    if not API_COSTS_PATH.exists():
        return 0.0
    total = 0.0
    with open(API_COSTS_PATH) as f:
        for line in f:
            try:
                total += float(json.loads(line).get("cost_usd", 0))
            except Exception:
                pass
    return round(total, 2)


def get_today_api_cost():
    if not API_COSTS_PATH.exists():
        return 0.0
    today = date.today().isoformat()
    total = 0.0
    with open(API_COSTS_PATH) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("date") == today:
                    total += float(entry.get("cost_usd", 0))
            except Exception:
                pass
    return round(total, 2)


def print_metrics(full=False):
    trades = load_trades()

    if not trades:
        print("\n  No trades yet. Run the bot in dry mode to see simulated trades.")
        return

    all_settled = [t for t in trades if t.get("status") in ("win", "loss")]
    all_open = [t for t in trades if t.get("status") == "open"]
    dry_trades = [t for t in all_settled if t.get("mode") == "dry"]
    live_trades = [t for t in all_settled if t.get("mode") == "live"]

    # P&L series
    pnl_series = []
    running_pnl = 0.0
    for t in all_settled:
        pnl = estimate_pnl(t)
        t["_pnl"] = pnl
        running_pnl += pnl
        pnl_series.append(running_pnl)

    # Core stats
    n = len(all_settled)
    wins = sum(1 for t in all_settled if t["status"] == "win")
    losses = n - wins
    win_rate = wins / n if n > 0 else 0

    total_wagered = sum(t["bet_usd"] for t in all_settled)
    total_pnl = sum(t["_pnl"] for t in all_settled)
    max_dd = calculate_max_drawdown(pnl_series)

    # Load bankroll from config
    try:
        with open(ROOT / "config.json") as f:
            cfg = json.load(f)
        bankroll = cfg["risk"]["bankroll_usd"]
    except Exception:
        bankroll = 750

    max_dd_pct = max_dd / bankroll if bankroll > 0 else 0

    # Sharpe (returns as fraction of bankroll per trade)
    returns = [t["_pnl"] / bankroll for t in all_settled]
    sharpe = calculate_sharpe(returns)

    # Profit Factor
    gross_profit = sum(t["_pnl"] for t in all_settled if t["_pnl"] > 0)
    gross_loss = abs(sum(t["_pnl"] for t in all_settled if t["_pnl"] < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    # Brier Score
    brier = calculate_brier_score(all_settled)

    # API costs
    api_cost_total = get_total_api_cost()
    api_cost_today = get_today_api_cost()

    # Target flags
    def flag(value, target, higher_better=True):
        if higher_better:
            return "✅" if value >= target else "⚠️ "
        else:
            return "✅" if value <= target else "⚠️ "

    print(f"\n{'='*60}")
    print(f"  PSYCO CAPITAL — BOT PERFORMANCE METRICS")
    print(f"  As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    print(f"\n  TRADE SUMMARY")
    print(f"  Total settled:  {n}  ({len(dry_trades)} dry / {len(live_trades)} live)")
    print(f"  Open positions: {len(all_open)}")
    print(f"  Total wagered:  ${total_wagered:.2f}")
    print(f"  Net P&L:        ${total_pnl:+.2f}")

    print(f"\n  PERFORMANCE  (targets from config)")
    print(f"  {flag(win_rate, 0.60)} Win Rate:       {win_rate:.1%}   (target ≥60%)")
    print(f"  {flag(sharpe, 2.0)} Sharpe Ratio:   {sharpe:.2f}    (target ≥2.0)")
    print(f"  {flag(profit_factor, 1.5)} Profit Factor:  {profit_factor:.2f}    (target ≥1.5)")
    if brier is not None:
        print(f"  {flag(brier, 0.25, higher_better=False)} Brier Score:    {brier:.4f}  (target <0.25, lower=better)")
    print(f"  {flag(max_dd_pct, 0.08, higher_better=False)} Max Drawdown:   {max_dd_pct:.1%}   (block at 8%)")

    print(f"\n  API COSTS")
    print(f"  Today:          ${api_cost_today:.2f}  (limit $50/day)")
    print(f"  All-time:       ${api_cost_total:.2f}")

    if len(all_open) > 0:
        exposure = sum(t["bet_usd"] for t in all_open)
        print(f"\n  OPEN EXPOSURE:  ${exposure:.2f}")
        for t in all_open:
            mode_tag = "[DRY] " if t.get("mode") == "dry" else ""
            print(f"    {mode_tag}{t['direction']} {t['question'][:45]} — ${t['bet_usd']:.2f}")

    if full and all_settled:
        print(f"\n  TRADE LOG")
        for t in all_settled[-20:]:
            icon = "✅" if t["status"] == "win" else "❌"
            pnl_str = f"${t['_pnl']:+.2f}"
            mode_tag = "[D]" if t.get("mode") == "dry" else "[L]"
            print(f"  {icon} {mode_tag} {t['question'][:40]} | "
                  f"{t['direction']} ${t['bet_usd']:.2f} | {pnl_str}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Show per-trade breakdown")
    args = parser.parse_args()
    print_metrics(full=args.full)
