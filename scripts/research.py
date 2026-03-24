#!/usr/bin/env python3
"""
Agent 2: Research (Parallel Threads)
Scrapes CryptoPanic, Reddit, CoinGecko, and web search per flagged market.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger("polybot.research")

CRYPTOPANIC_API = "https://cryptopanic.com/api/v1/posts/"
REDDIT_API = "https://www.reddit.com/search.json"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Asset name → CoinGecko ID mapping for common crypto
ASSET_MAP = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana": "solana", "sol": "solana",
    "xrp": "ripple", "ripple": "ripple",
    "cardano": "cardano", "ada": "cardano",
    "binance": "binancecoin", "bnb": "binancecoin",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "polygon": "matic-network", "matic": "matic-network",
}


def extract_asset(question):
    """Attempt to identify the primary asset from a market question."""
    q = question.lower()
    for keyword, coin_id in ASSET_MAP.items():
        if keyword in q:
            return keyword, coin_id
    return None, None


def score_sentiment(texts):
    """Simple keyword-based sentiment scoring. Returns -1.0 to 1.0."""
    BULL = ["bullish", "surge", "rally", "gain", "moon", "pump", "up", "higher",
            "buy", "long", "positive", "growth", "rise", "strong", "beat"]
    BEAR = ["bearish", "crash", "dump", "drop", "down", "sell", "short", "negative",
            "decline", "fall", "weak", "miss", "loss", "fear", "panic", "correction"]
    pos, neg, total = 0, 0, 0
    for text in texts:
        t = text.lower()
        for w in BULL:
            if w in t:
                pos += 1
        for w in BEAR:
            if w in t:
                neg += 1
        total += 1
    if total == 0:
        return 0.0
    return round((pos - neg) / max(pos + neg, 1), 2)


def fetch_cryptopanic(question, api_key):
    """Fetch recent news from CryptoPanic for the market topic."""
    # Extract key terms from question (first 3-4 words usually enough)
    words = [w for w in question.split() if len(w) > 3][:4]
    search_term = " ".join(words)

    try:
        params = {"auth_token": api_key, "filter": "hot", "public": "true"}
        if api_key:
            params["filter"] = "important"
        resp = requests.get(CRYPTOPANIC_API, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])

        # Filter to relevant headlines
        relevant = [r["title"] for r in results
                    if any(w.lower() in r.get("title", "").lower() for w in words)][:10]
        return relevant
    except Exception as e:
        log.warning(f"CryptoPanic fetch failed: {e}")
        return []


def fetch_reddit_sentiment(question):
    """Search Reddit for recent discussion on the market topic."""
    words = [w for w in question.split() if len(w) > 3][:3]
    query = " ".join(words)

    headers = {"User-Agent": "polybot/1.0 (research agent)"}
    texts = []
    bull_count, bear_count = 0, 0

    for sub in ["CryptoCurrency", "ethfinance", "BitcoinMarkets", "wallstreetbets"]:
        try:
            resp = requests.get(
                f"{REDDIT_API}",
                params={"q": query, "subreddit": sub, "sort": "new",
                        "t": "day", "limit": 15},
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                title = post["data"].get("title", "")
                texts.append(title)
        except Exception as e:
            log.debug(f"Reddit fetch failed for r/{sub}: {e}")

    if not texts:
        return 0.5  # neutral if no data

    sentiment = score_sentiment(texts)
    # Convert -1/+1 to 0/1 ratio for consistency
    bull_ratio = (sentiment + 1) / 2
    return round(bull_ratio, 2)


def fetch_coingecko(coin_id):
    """Fetch 7-day price trend for a coin."""
    if not coin_id:
        return "unknown"
    try:
        resp = requests.get(
            f"{COINGECKO_API}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": 7, "interval": "daily"},
            timeout=10
        )
        resp.raise_for_status()
        prices = [p[1] for p in resp.json().get("prices", [])]
        if len(prices) < 2:
            return "unknown"
        change = (prices[-1] - prices[0]) / prices[0]
        if change > 0.10:
            return "strong_up"
        elif change > 0.03:
            return "up"
        elif change < -0.10:
            return "strong_down"
        elif change < -0.03:
            return "down"
        else:
            return "flat"
    except Exception as e:
        log.debug(f"CoinGecko fetch failed for {coin_id}: {e}")
        return "unknown"


def research_one_market(market, cfg):
    """Run all research threads for a single market. Returns research dict."""
    question = market["question"]
    asset_name, coin_id = extract_asset(question)
    api_key = cfg.get("apis", {}).get("cryptopanic_key", "")

    log.info(f"  Researching: {question[:60]}...")

    # Run all fetches (could be truly parallel with ThreadPoolExecutor within this func)
    news_headlines = fetch_cryptopanic(question, api_key)
    reddit_bull_ratio = fetch_reddit_sentiment(question)
    price_trend = fetch_coingecko(coin_id)

    sentiment_score = score_sentiment(news_headlines) if news_headlines else 0.0
    news_summary = "; ".join(news_headlines[:3]) if news_headlines else "No relevant news found."

    return {
        **market,
        "sentiment_score": sentiment_score,
        "reddit_bull_ratio": reddit_bull_ratio,
        "price_trend": price_trend,
        "news_headlines": news_headlines[:5],
        "news_summary": news_summary,
        "asset": asset_name,
        "researched_at": datetime.utcnow().isoformat(),
    }


def run_research(flagged_markets, cfg):
    """
    Run research in parallel across all flagged markets.
    Returns list of enriched market dicts.
    """
    max_workers = min(len(flagged_markets), cfg.get("research", {}).get("max_parallel", 5))
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(research_one_market, m, cfg): m
            for m in flagged_markets
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log.error(f"Research failed for market: {e}")

    return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
    with open("config.json") as f:
        cfg = json.load(f)
    # Test with a dummy market
    test_markets = [{"market_id": "test", "question": "Will Bitcoin exceed $100k by end of March?",
                     "yes_price": 0.42, "liquidity": 50000, "volume_24h": 12000,
                     "resolution_days": 14, "tags": [], "scanned_at": datetime.utcnow().isoformat()}]
    results = run_research(test_markets, cfg)
    print(json.dumps(results, indent=2))
