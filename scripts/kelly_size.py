#!/usr/bin/env python3
"""
kelly_size.py — Kelly Criterion Position Calculator
Deterministic sizing script. Called by risk.py before execution.

Formulas from the guide:
  Full Kelly:      f* = (p * b - q) / b
  Fractional Kelly: f  = f* * alpha  (alpha = 0.25 for quarter-Kelly)
  VaR:             VaR = bet_usd * 1.645  (95% confidence)
  Max Drawdown:    MDD = (Peak - Trough) / Peak
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).parent.parent


def kelly_fraction(p: float, b: float) -> float:
    """
    Calculate full Kelly fraction.
    p = win probability (your model estimate)
    b = net odds (what you win per $1 bet; for binary market: (1 - price) / price)
    Returns fraction of bankroll to bet (0 to 1).
    """
    if p <= 0 or p >= 1 or b <= 0:
        return 0.0
    q = 1 - p
    f = (p * b - q) / b
    return max(f, 0.0)


def fractional_kelly(p: float, b: float, alpha: float = 0.25) -> float:
    """
    Quarter-Kelly by default (alpha=0.25).
    Most professional traders use 0.25-0.50 to reduce variance.
    Full Kelly is mathematically optimal but extremely volatile in practice.
    """
    return kelly_fraction(p, b) * alpha


def calculate_bet_size(
    true_prob: float,
    market_price: float,
    bankroll: float,
    direction: str,
    cfg: dict
) -> dict:
    """
    Calculate the appropriate bet size for a trade.
    
    Returns a dict with:
      bet_usd       — recommended bet in dollars
      kelly_full    — full Kelly fraction
      kelly_applied — fraction actually used (quarter-Kelly, capped)
      b             — net odds
      var_usd       — Value at Risk at 95% confidence
      reasoning     — human-readable explanation
    """
    risk_cfg = cfg["risk"]
    alpha = risk_cfg["max_bet_fraction"]  # 0.25 = quarter-Kelly

    # Net odds: if you bet $1 on YES at price 0.38, you win (1-0.38)/0.38 = $1.63
    if direction == "YES":
        price = market_price
    else:
        price = 1 - market_price

    if price <= 0 or price >= 1:
        return {"bet_usd": 0, "reasoning": "Invalid price"}

    b = (1 - price) / price  # net odds multiplier

    # Kelly sizing — win probability is true_prob for YES bets, (1 - true_prob) for NO bets
    win_prob = true_prob if direction == "YES" else (1 - true_prob)
    kelly_full = kelly_fraction(win_prob, b)
    kelly_applied_fraction = fractional_kelly(win_prob, b, alpha)

    # Dollar amounts
    bet_raw = bankroll * kelly_applied_fraction

    # Apply caps
    max_single = bankroll * risk_cfg["max_single_position_pct"]  # 5% of bankroll
    hard_cap = risk_cfg["max_bet_usd_hard_cap"]
    bet_usd = min(bet_raw, max_single, hard_cap)
    bet_usd = max(bet_usd, 0)  # no negative bets
    bet_usd = round(bet_usd, 2)

    # Value at Risk at 95% confidence
    # Binary outcome: lose entire bet with (1-true_prob) probability
    # VaR = bet_usd * z_95 where z_95 = 1.645
    var_usd = round(bet_usd * 1.645, 2)

    # Expected Value
    ev = true_prob * (bet_usd * b) - (1 - true_prob) * bet_usd
    ev = round(ev, 2)

    reasoning = (
        f"Bankroll ${bankroll:.0f} | "
        f"Price {price:.0%} | "
        f"Win prob {win_prob:.0%} ({direction}) | "
        f"Net odds {b:.2f}x | "
        f"Full Kelly {kelly_full:.1%} → "
        f"Quarter-Kelly {kelly_applied_fraction:.1%} → "
        f"Raw ${bet_raw:.2f} → "
        f"Capped ${bet_usd:.2f} | "
        f"EV ${ev:+.2f} | "
        f"VaR(95%) ${var_usd:.2f}"
    )

    return {
        "bet_usd": bet_usd,
        "kelly_full": round(kelly_full, 4),
        "kelly_applied": round(kelly_applied_fraction, 4),
        "b": round(b, 4),
        "ev_usd": ev,
        "var_usd": var_usd,
        "reasoning": reasoning,
    }


def calculate_brier_score(predictions: list[dict]) -> float:
    """
    Brier Score = (1/n) * sum((predicted_prob - actual_outcome)^2)
    Lower is better. Target: < 0.25
    predictions: list of {"predicted": float, "outcome": 1 or 0}
    """
    if not predictions:
        return None
    n = len(predictions)
    total = sum((p["predicted"] - p["outcome"]) ** 2 for p in predictions)
    return round(total / n, 4)


def calculate_sharpe(returns: list[float], risk_free: float = 0.0) -> float:
    """
    Sharpe Ratio = (mean_return - risk_free) / std_return
    Target: > 2.0
    returns: list of trade P&L as fraction of bankroll
    """
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean_r = sum(returns) / n
    variance = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return round((mean_r - risk_free) / std_r, 3)


def calculate_profit_factor(trades: list[dict]) -> float:
    """
    Profit Factor = gross_profit / gross_loss
    Target: > 1.5
    """
    gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
    if gross_loss == 0:
        return float("inf")
    return round(gross_profit / gross_loss, 3)


if __name__ == "__main__":
    # Demo calculation
    with open(ROOT / "config.json") as f:
        cfg = json.load(f)

    print("=== Kelly Sizing Demo ===\n")

    # Example: BTC over $100k market at 42%, we think it's 55%
    result = calculate_bet_size(
        true_prob=0.55,
        market_price=0.42,
        bankroll=750,
        direction="YES",
        cfg=cfg
    )
    print(f"Bet size: ${result['bet_usd']}")
    print(f"Reasoning: {result['reasoning']}")
    print()

    # Brier Score example
    sample_predictions = [
        {"predicted": 0.70, "outcome": 1},
        {"predicted": 0.60, "outcome": 1},
        {"predicted": 0.45, "outcome": 0},
        {"predicted": 0.80, "outcome": 0},  # bad prediction
        {"predicted": 0.55, "outcome": 1},
    ]
    bs = calculate_brier_score(sample_predictions)
    print(f"Brier Score: {bs} (target < 0.25, lower is better)")
