#!/usr/bin/env python3
"""
positions.py / review.py
View open positions and daily trade summaries.
"""

import json
import sys
import argparse
from datetime import datetime, date, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRADES_PATH = ROOT / "logs" / "trades.jsonl"
LEARNINGS_PATH = ROOT / "logs" / "learnings.jsonl"


def load_trades():
    trades = []
    if not TRADES_PATH.exists():
        return trades
    with open(TRADES_PATH) as f:
        for line in f:
            try:
                trades.append(json.loads(line))
            except Exception:
                pass
    return trades


def format_status(status):
    icons = {"open": "🟡", "win": "✅", "loss": "❌", "dry": "🔵"}
    return f"{icons.get(status, '?')} {status.upper()}"


def show_positions():
    trades = load_trades()
    open_trades = [t for t in trades if t.get("status") == "open"]

    print(f"\n{'='*60}")
    print(f"  OPEN POSITIONS ({len(open_trades)})")
    print(f"{'='*60}")

    if not open_trades:
        print("  No open positions.")
    else:
        total_exposure = 0
        for t in open_trades:
            mode_tag = "[DRY] " if t.get("mode") == "dry" else ""
            print(f"\n  {mode_tag}{t['question'][:55]}")
            print(f"  → {t['direction']} | ${t['bet_usd']:.2f} @ {t['entry_price']:.0%} "
                  f"| edge={t['edge']:.2%} | conf={t['confidence']:.0%}")
            print(f"  → Entered: {t['timestamp'][:19]} | ID: {t['trade_id']}")
            total_exposure += t.get("bet_usd", 0)
        print(f"\n  Total exposure: ${total_exposure:.2f}")

    # Summary stats
    settled = [t for t in trades if t.get("status") in ("win", "loss")]
    if settled:
        wins = sum(1 for t in settled if t["status"] == "win")
        losses = len(settled) - wins
        win_rate = wins / len(settled) if settled else 0
        total_bet = sum(t.get("bet_usd", 0) for t in settled)
        print(f"\n  Historical: {wins}W / {losses}L | Win rate: {win_rate:.0%} | "
              f"Total bet: ${total_bet:.2f}")

    print()


def show_today():
    trades = load_trades()
    today = date.today().isoformat()
    today_trades = [t for t in trades if t.get("timestamp", "")[:10] == today]

    print(f"\n{'='*60}")
    print(f"  TODAY'S TRADES ({today})")
    print(f"{'='*60}")

    if not today_trades:
        print("  No trades placed today.")
    else:
        for t in today_trades:
            mode_tag = "[DRY] " if t.get("mode") == "dry" else ""
            status_icon = format_status(t.get("status", "open"))
            print(f"\n  {status_icon} {mode_tag}{t['question'][:50]}")
            print(f"  → {t['direction']} ${t['bet_usd']:.2f} @ {t['entry_price']:.0%} "
                  f"| Dominant signal: {t.get('dominant_signal', '?')}")
            if t.get("reasoning"):
                print(f"  → Reasoning: {t['reasoning'][:100]}")

    # Load today's learnings
    learnings = []
    if LEARNINGS_PATH.exists():
        with open(LEARNINGS_PATH) as f:
            for line in f:
                try:
                    l = json.loads(line)
                    if l.get("date", "")[:10] == today:
                        learnings.append(l)
                except Exception:
                    pass

    if learnings:
        print(f"\n  POST-MORTEMS TODAY ({len(learnings)}):")
        for l in learnings:
            print(f"  ❌ [{l['error_type']}] {l['market'][:50]}")
            print(f"     Lesson: {l['lesson']}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true", help="Show open positions")
    parser.add_argument("--today", action="store_true", help="Show today's trades")
    parser.add_argument("--all", action="store_true", help="Show all trades")
    args = parser.parse_args()

    if args.status or not any([args.today, args.all]):
        show_positions()
    if args.today:
        show_today()
    if args.all:
        trades = load_trades()
        print(json.dumps(trades, indent=2))
