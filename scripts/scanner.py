#!/usr/bin/env python3
"""
Agent 1: Market Scanner
Polls Polymarket API, filters to crypto/finance, flags opportunities.
"""

import json
import logging
import os
import requests
from datetime import datetime, timedelta, timezone

log = logging.getLogger("polybot.scanner")

POLYMARKET_API = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "solana", "sol", "defi", "stablecoin", "usdc", "usdt",
    "coinbase", "binance", "exchange", "altcoin", "halving",
    "sec", "etf", "price", "market cap", "liquidation", "fed",
    "interest rate", "inflation", "cpi", "gdp", "nasdaq", "s&p", "tariff",
    "recession", "treasury", "dollar", "economy",
    "presidential", "election", "nomination", "democrat", "republican",
    "congress", "senate", "president", "primary",
    "win the 2028", "win the 2026",
    "nba finals", "world cup", "super bowl", "championship",
    "fifa", "nfl", "mlb", "nhl",
]


def fetch_markets(limit=300):
    """Fetch active markets from Polymarket Gamma API."""
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={"active": "true", "closed": "false", "limit": limit},
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Failed to fetch markets: {e}")
        return []


def fetch_market_price(condition_id):
    """Fetch current price data for a market."""
    try:
        resp = requests.get(
            f"{POLYMARKET_API}/book",
            params={"token_id": condition_id},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning(f"Price fetch failed for {condition_id}: {e}")
        return None


def is_crypto_finance(market):
    """Check if market question is related to crypto/finance."""
    question = market.get("question", "").lower()
    description = market.get("description", "").lower()
    tags = [t.lower() for t in market.get("tags", [])]

    combined = question + " " + description + " " + " ".join(tags)
    return any(kw in combined for kw in CRYPTO_KEYWORDS)


def calculate_spread(price_data):
    """Calculate bid-ask spread as percentage."""
    if not price_data:
        return 1.0
    bids = price_data.get("bids", [])
    asks = price_data.get("asks", [])
    if not bids or not asks:
        return 1.0
    best_bid = float(bids[0]["price"])
    best_ask = float(asks[0]["price"])
    mid = (best_bid + best_ask) / 2
    if mid == 0:
        return 1.0
    return (best_ask - best_bid) / mid


def get_resolution_days(market):
    """Return days until market resolution."""
    end_date_str = market.get("endDate") or market.get("end_date_iso")
    if not end_date_str:
        return None
    try:
        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (end_dt - now).days
    except Exception:
        return None


def flag_market(market, cfg):
    """Return True if market passes all scanner criteria."""
    scanner_cfg = cfg["scanner"]

    # Liquidity check
    liquidity = float(market.get("liquidity", 0))
    if liquidity < scanner_cfg["min_liquidity_usd"]:
        return False, "low_liquidity"

    # Volume check
    volume_24h = float(market.get("volume24hr", 0))
    if volume_24h < scanner_cfg["min_volume_24h"]:
        return False, "low_volume"

    # Resolution window check
    days = get_resolution_days(market)
    max_days = scanner_cfg.get("max_days_to_resolution", 30)
    if days is None or days < 1 or days > max_days:
        return False, "resolution_window"

    # Price sanity check (avoid near-certain outcomes)
    yes_price = float(market.get("lastTradePrice", 0.5))
    if yes_price < 0.05 or yes_price > 0.95:
        return False, "price_extreme"

    return True, "passed"


def run_scanner(cfg):
    """Main scanner entry point. Returns list of flagged market dicts."""
    log.info("Fetching Polymarket markets...")
    all_markets = fetch_markets(limit=300)
    log.info(f"  Fetched {len(all_markets)} total markets")

    # Filter to crypto/finance
    crypto_markets = [m for m in all_markets if is_crypto_finance(m)]
    log.info(f"  {len(crypto_markets)} crypto/finance markets found")

    flagged = []
    for market in crypto_markets:
        passed, reason = flag_market(market, cfg)
        if passed:
            flagged.append({
                "market_id": market.get("id") or market.get("conditionId"),
                "question": market.get("question"),
                "yes_price": float(market.get("lastTradePrice", 0.5)),
                "liquidity": float(market.get("liquidity", 0)),
                "volume_24h": float(market.get("volume24hr", 0)),
                "resolution_days": get_resolution_days(market),
                "tags": market.get("tags", []),
                "scanned_at": datetime.utcnow().isoformat(),
            })
        else:
            log.debug(f"  Skipped '{market.get('question', '')[:50]}': {reason}")

    log.info(f"  Scanner flagged {len(flagged)} markets for research")
    return flagged


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    with open("config.json") as f:
        cfg = json.load(f)
    results = run_scanner(cfg)
    print(json.dumps(results, indent=2))
