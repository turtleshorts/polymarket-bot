#!/usr/bin/env python3
"""
validate_risk.py — Deterministic Risk Checks
ALL checks must pass before any trade executes.
This is Python code, not language instructions — results are deterministic.

Called by risk.py before every order. Returns (passed: bool, reason: str).
"""

import json
import math
import os
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent.parent
TRADES_PATH = ROOT / "logs" / "trades.jsonl"


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


# ─────────────────────────────────────────────
# CHECK 1: Kill Switch
# ─────────────────────────────────────────────
def check_kill_switch(cfg) -> tuple[bool, str]:
    """If a file named STOP exists in the bot root, halt all trading."""
    kill_file = ROOT / cfg["bot"].get("kill_switch_file", "STOP")
    if kill_file.exists():
        return False, f"KILL SWITCH ACTIVE — delete '{kill_file.name}' to resume trading"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 2: Edge Threshold
# ─────────────────────────────────────────────
def check_edge(edge: float, cfg) -> tuple[bool, str]:
    """Edge must exceed minimum threshold to be worth trading."""
    min_edge = cfg["bot"]["min_edge"]
    if edge < min_edge:
        return False, f"Edge {edge:.2%} below minimum {min_edge:.2%}"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 3: Max Drawdown
# ─────────────────────────────────────────────
def check_max_drawdown(cfg) -> tuple[bool, str]:
    """Block all new trades if drawdown exceeds 8% of starting bankroll."""
    trades = load_trades()
    settled = [t for t in trades if t.get("status") in ("win", "loss")]
    if not settled:
        return True, "ok"

    bankroll = cfg["risk"]["bankroll_usd"]
    max_dd_pct = cfg["risk"]["max_drawdown_pct"]

    # Calculate running P&L
    pnl_series = []
    running = 0.0
    peak = 0.0
    for t in settled:
        if t["status"] == "win":
            # Approximate win: got back bet + edge * bet
            running += t["bet_usd"] * t.get("edge", 0.05)
        else:
            running -= t["bet_usd"]
        pnl_series.append(running)
        if running > peak:
            peak = running

    if pnl_series:
        trough = min(pnl_series)
        drawdown = (peak - trough) / bankroll if bankroll > 0 else 0
        if drawdown > max_dd_pct:
            return False, f"Max drawdown {drawdown:.1%} exceeds limit {max_dd_pct:.0%}. No new trades."

    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 4: Daily Loss Limit
# ─────────────────────────────────────────────
def check_daily_loss_limit(cfg) -> tuple[bool, str]:
    """Stop trading for the day if daily losses exceed threshold."""
    trades = load_trades()
    today = date.today().isoformat()
    today_settled = [
        t for t in trades
        if t.get("timestamp", "")[:10] == today
        and t.get("status") in ("win", "loss")
    ]

    bankroll = cfg["risk"]["bankroll_usd"]
    daily_limit = bankroll * cfg["risk"]["daily_loss_limit_pct"]

    daily_pnl = 0.0
    for t in today_settled:
        if t["status"] == "win":
            daily_pnl += t["bet_usd"] * t.get("edge", 0.05)
        else:
            daily_pnl -= t["bet_usd"]

    if daily_pnl < -daily_limit:
        return False, f"Daily loss ${abs(daily_pnl):.2f} exceeds limit ${daily_limit:.2f}. Stopped for today."

    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 5: Position Size (Kelly + Hard Cap)
# ─────────────────────────────────────────────
def check_position_size(bet_usd: float, bankroll: float, cfg) -> tuple[bool, str]:
    """Bet must not exceed 5% of bankroll or hard cap."""
    max_single_pct = cfg["risk"]["max_single_position_pct"]
    hard_cap = cfg["risk"]["max_bet_usd_hard_cap"]

    max_by_pct = bankroll * max_single_pct
    effective_max = min(max_by_pct, hard_cap)

    if bet_usd > effective_max:
        return False, f"Bet ${bet_usd:.2f} exceeds max ${effective_max:.2f} (5% bankroll or hard cap)"
    if bet_usd < cfg["risk"]["min_bet_usd"]:
        return False, f"Bet ${bet_usd:.2f} below minimum ${cfg['risk']['min_bet_usd']}"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 6: Total Exposure
# ─────────────────────────────────────────────
def check_total_exposure(bet_usd: float, open_positions: list, bankroll: float, cfg) -> tuple[bool, str]:
    """Total open exposure must stay under 15% of bankroll."""
    max_exposure_pct = cfg["risk"]["max_total_exposure_fraction"]
    max_exposure_usd = bankroll * max_exposure_pct
    current_exposure = sum(float(p.get("bet_usd", 0)) for p in open_positions)

    if current_exposure + bet_usd > max_exposure_usd:
        return False, (
            f"Total exposure ${current_exposure + bet_usd:.2f} would exceed "
            f"limit ${max_exposure_usd:.2f} ({max_exposure_pct:.0%} of bankroll)"
        )
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 7: Max Concurrent Positions
# ─────────────────────────────────────────────
def check_concurrent_positions(open_positions: list, cfg) -> tuple[bool, str]:
    max_pos = cfg["risk"]["max_concurrent_positions"]
    if len(open_positions) >= max_pos:
        return False, f"Already at max concurrent positions ({max_pos})"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 8: Value at Risk (VaR)
# ─────────────────────────────────────────────
def check_var(bet_usd: float, bankroll: float, cfg) -> tuple[bool, str]:
    """
    Simple VaR check: at 95% confidence, max daily loss must stay within limit.
    VaR = bet_usd * 1.645 (z-score for 95% confidence on binary outcome)
    """
    var_limit = bankroll * cfg["risk"]["var_daily_limit_pct"]
    var_this_trade = bet_usd * 1.645  # 95% confidence z-score

    if var_this_trade > var_limit:
        return False, f"VaR ${var_this_trade:.2f} exceeds daily limit ${var_limit:.2f}"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 9: Daily API Cost Cap
# ─────────────────────────────────────────────
def check_api_cost(cfg) -> tuple[bool, str]:
    """Prevent runaway API costs — check log for today's estimated spend."""
    cost_log = ROOT / "logs" / "api_costs.jsonl"
    if not cost_log.exists():
        return True, "ok"

    today = date.today().isoformat()
    daily_cost = 0.0
    with open(cost_log) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("date") == today:
                    daily_cost += float(entry.get("cost_usd", 0))
            except Exception:
                pass

    max_cost = cfg["risk"]["max_daily_api_cost_usd"]
    if daily_cost >= max_cost:
        return False, f"Daily API cost ${daily_cost:.2f} reached limit ${max_cost:.2f}"
    return True, "ok"


# ─────────────────────────────────────────────
# CHECK 10: Duplicate Position
# ─────────────────────────────────────────────
def check_no_duplicate(market_id: str, open_positions: list) -> tuple[bool, str]:
    """Don't open a second position in the same market."""
    if any(p.get("market_id") == market_id for p in open_positions):
        return False, f"Already have open position in market {market_id}"
    return True, "ok"


# ─────────────────────────────────────────────
# MASTER VALIDATOR
# ─────────────────────────────────────────────
def validate_all(opportunity: dict, open_positions: list, bet_usd: float, cfg) -> tuple[bool, str]:
    """
    Run all risk checks in order. Returns (True, "ok") only if ALL pass.
    First failure short-circuits — returns immediately with the reason.
    """
    bankroll = cfg["risk"]["bankroll_usd"]
    market_id = opportunity["market_id"]
    edge = opportunity.get("edge", 0)

    checks = [
        lambda: check_kill_switch(cfg),
        lambda: check_edge(edge, cfg),
        lambda: check_max_drawdown(cfg),
        lambda: check_daily_loss_limit(cfg),
        lambda: check_no_duplicate(market_id, open_positions),
        lambda: check_concurrent_positions(open_positions, cfg),
        lambda: check_position_size(bet_usd, bankroll, cfg),
        lambda: check_total_exposure(bet_usd, open_positions, bankroll, cfg),
        lambda: check_var(bet_usd, bankroll, cfg),
        lambda: check_api_cost(cfg),
    ]

    for check in checks:
        passed, reason = check()
        if not passed:
            return False, reason

    return True, "ok"


if __name__ == "__main__":
    # Quick test
    with open(ROOT / "config.json") as f:
        cfg = json.load(f)

    test_opp = {"market_id": "test-123", "edge": 0.12, "direction": "YES"}
    test_positions = []
    test_bet = 30.0

    passed, reason = validate_all(test_opp, test_positions, test_bet, cfg)
    print(f"Validation: {'✅ PASS' if passed else '❌ FAIL'} — {reason}")

    # Test kill switch
    kill_file = ROOT / "STOP"
    kill_file.touch()
    passed, reason = validate_all(test_opp, test_positions, test_bet, cfg)
    print(f"Kill switch test: {'✅ PASS' if passed else '❌ BLOCKED'} — {reason}")
    kill_file.unlink()
    print("Kill switch removed.")
