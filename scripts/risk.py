#!/usr/bin/env python3
"""
Agent 4: Risk Sizing & Execution
Uses validate_risk.py for deterministic checks and kelly_size.py for sizing.
Places orders via Polymarket CLOB or Kalshi REST API.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests

from scripts.validate_risk import validate_all
from scripts.kelly_size import calculate_bet_size

log = logging.getLogger("polybot.risk")

ROOT = Path(__file__).parent.parent
TRADES_PATH = ROOT / "logs" / "trades.jsonl"

POLYMARKET_API = "https://clob.polymarket.com"
KALSHI_API = "https://trading-api.kalshi.com/trade-api/v2"


def get_current_bankroll(cfg):
    try:
        wallet_address = os.environ.get("POLYGON_ADDRESS") or cfg.get("wallet", {}).get("address")
        if not wallet_address or wallet_address == "SET_IN_ENV_FILE":
            return cfg["risk"]["bankroll_usd"]
        resp = requests.get(
            f"{POLYMARKET_API}/balance",
            headers={"CLOB-API-KEY": os.environ.get("POLYMARKET_API_KEY", "")},
            params={"wallet": wallet_address},
            timeout=10
        )
        resp.raise_for_status()
        return float(resp.json().get("balance", cfg["risk"]["bankroll_usd"]))
    except Exception as e:
        log.warning(f"Could not fetch live balance, using config value: {e}")
        return cfg["risk"]["bankroll_usd"]


def place_order_polymarket(market_id, direction, bet_usd, price, cfg):
    api_key = os.environ.get("POLYMARKET_API_KEY")
    private_key = os.environ.get("POLYGON_PRIVATE_KEY")
    if not api_key or not private_key:
        log.error("Missing POLYMARKET_API_KEY or POLYGON_PRIVATE_KEY")
        return None

    # Check slippage: re-fetch current price before placing
    # (simplified — production would check live orderbook)
    size_usdc = int(bet_usd * 1_000_000)
    payload = {
        "market": market_id,
        "side": direction,
        "price": round(price, 4),
        "size": size_usdc,
        "type": "LIMIT",
        "time_in_force": "GTC",
    }
    try:
        resp = requests.post(
            f"{POLYMARKET_API}/order",
            json=payload,
            headers={"CLOB-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Polymarket order failed: {e}")
        return None


def place_order_kalshi(market_id, direction, bet_usd, price, cfg):
    """
    Kalshi order placement.
    Kalshi uses cents (integer), YES/NO sides, and their own auth header format.
    Set KALSHI_API_KEY and KALSHI_API_SECRET in .env.
    """
    api_key = os.environ.get("KALSHI_API_KEY")
    if not api_key:
        log.warning("KALSHI_API_KEY not set, skipping Kalshi execution")
        return None

    # Kalshi uses cents for price (0-100 scale)
    price_cents = int(round(price * 100))
    count = max(1, int(bet_usd / price))  # number of contracts

    payload = {
        "ticker": market_id,
        "client_order_id": str(uuid.uuid4()),
        "type": "limit",
        "action": "buy",
        "side": direction.lower(),  # "yes" or "no"
        "count": count,
        "yes_price": price_cents if direction == "YES" else None,
        "no_price": price_cents if direction == "NO" else None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        resp = requests.post(
            f"{KALSHI_API}/portfolio/orders",
            json=payload,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Kalshi order failed: {e}")
        return None


def log_trade(trade_record):
    TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADES_PATH, "a") as f:
        f.write(json.dumps(trade_record) + "\n")


def run_risk_and_execute(opportunity, open_positions, cfg, mode="dry"):
    direction = opportunity["direction"]
    yes_price = opportunity["yes_price"]
    price = yes_price if direction == "YES" else (1 - yes_price)
    bankroll = get_current_bankroll(cfg)
    exchange = opportunity.get("exchange", "polymarket")

    # Calculate Kelly-based bet size
    sizing = calculate_bet_size(
        true_prob=opportunity["true_prob"],
        market_price=yes_price,
        bankroll=bankroll,
        direction=direction,
        cfg=cfg
    )
    bet_usd = sizing["bet_usd"]

    # Add bet_usd to opportunity dict so validate_all can see it
    opportunity_with_bet = {**opportunity, "bet_usd": bet_usd}

    # Run ALL deterministic risk checks
    passed, reason = validate_all(opportunity_with_bet, open_positions, bet_usd, cfg)

    if not passed:
        log.info(f"  BLOCKED: {reason}")
        return None

    log.info(
        f"  {'[DRY]' if mode == 'dry' else '[LIVE]'} TRADE: "
        f"{direction} '{opportunity['question'][:45]}' | "
        f"${bet_usd:.2f} @ {price:.0%} | "
        f"edge={opportunity['edge']:.2%} conf={opportunity['confidence']:.0%} | "
        f"{exchange.upper()}"
    )
    log.info(f"  Sizing: {sizing['reasoning']}")

    # Execute
    order_result = None
    if mode == "live":
        if exchange == "kalshi":
            order_result = place_order_kalshi(
                opportunity["market_id"], direction, bet_usd, price, cfg
            )
        else:
            order_result = place_order_polymarket(
                opportunity["market_id"], direction, bet_usd, price, cfg
            )

        if order_result is None:
            log.error("  Order placement failed. Not recording position.")
            return None

    calibration = opportunity.get("calibration", {})
    trade_record = {
        "trade_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.utcnow().isoformat(),
        "mode": mode,
        "exchange": exchange,
        "market_id": opportunity["market_id"],
        "question": opportunity["question"],
        "direction": direction,
        "bet_usd": bet_usd,
        "entry_price": round(price, 4),
        "true_prob_estimate": opportunity["true_prob"],
        "edge": opportunity["edge"],
        "confidence": opportunity["confidence"],
        "kelly_full": sizing["kelly_full"],
        "kelly_applied": sizing["kelly_applied"],
        "ev_usd": sizing["ev_usd"],
        "var_usd": sizing["var_usd"],
        "bankroll_at_entry": bankroll,
        "dominant_signal": calibration.get("dominant_signal", "unknown"),
        "signal_agreement": opportunity.get("signal_agreement", "unknown"),
        "model_votes": opportunity.get("model_votes", []),
        "reasoning": calibration.get("reasoning", ""),
        # Research signals saved for post-mortem
        "sentiment_score": opportunity.get("sentiment_score"),
        "reddit_bull_ratio": opportunity.get("reddit_bull_ratio"),
        "price_trend": opportunity.get("price_trend"),
        "news_summary": opportunity.get("news_summary"),
        "status": "open",
        "order_result": order_result,
    }

    log_trade(trade_record)
    open_positions.append(trade_record)
    return trade_record
