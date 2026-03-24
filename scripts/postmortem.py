#!/usr/bin/env python3
"""
Agent 5: Post-Mortem Analysis
Triggered after settled losses. Extracts lessons and saves to learnings.jsonl.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import anthropic

log = logging.getLogger("polybot.postmortem")

ROOT = Path(__file__).parent.parent
TRADES_PATH = ROOT / "logs" / "trades.jsonl"
LEARNINGS_PATH = ROOT / "logs" / "learnings.jsonl"

POSTMORTEM_PROMPT = """You are a trading analyst reviewing a losing prediction market trade to extract lessons.

TRADE DETAILS:
- Question: {question}
- Our bet: {direction} at {entry_price:.0%}
- Our true probability estimate: {true_prob_estimate:.0%}
- Actual resolution: {resolution} (we lost)
- Edge we thought we had: {edge:.2%}
- Confidence level: {confidence:.0%}
- Dominant signal that drove the trade: {dominant_signal}
- Our reasoning at the time: {reasoning}

RESEARCH SIGNALS WE HAD:
- News sentiment: {sentiment_score}
- Reddit bull ratio: {reddit_bull_ratio}
- Price trend: {price_trend}
- News summary: {news_summary}

TASK:
Analyze what went wrong. Be specific and actionable. Classify the error type.

Error types:
- SENTIMENT_WRONG: Social/news sentiment was misleading
- TIMING_WRONG: Bet was directionally correct but wrong time window
- CALIBRATION_TOO_HIGH: We overestimated our edge / confidence
- FALSE_EDGE: The edge we saw wasn't real (market was efficient)
- MARKET_MANIPULATION: Price moved in ways consistent with wash trading
- SIGNAL_CONFLICT_IGNORED: Conflicting signals existed and we ignored the right one
- EXTERNAL_SHOCK: Unforeseeable event caused the loss (acceptable)

Respond ONLY with valid JSON:
{{
  "error_type": "ONE_OF_ABOVE",
  "what_we_thought": "Brief description of our thesis",
  "what_happened": "What actually caused us to lose",
  "lesson": "Specific, actionable lesson for future trades (1-2 sentences)",
  "signal_to_distrust": "which signal led us astray (or 'none' if external shock)",
  "weight_adjustment": "How to adjust signal weighting going forward",
  "acceptable_loss": true or false
}}"""


def load_all_trades():
    """Load all trade records from trades.jsonl."""
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


def update_trade_status(trade_id, status):
    """Update a trade's status in trades.jsonl (rewrite file)."""
    trades = load_all_trades()
    for t in trades:
        if t["trade_id"] == trade_id:
            t["status"] = status
            t["settled_at"] = datetime.utcnow().isoformat()

    with open(TRADES_PATH, "w") as f:
        for t in trades:
            f.write(json.dumps(t) + "\n")


def run_postmortem(trade, resolution, cfg):
    """
    Run post-mortem analysis on a settled losing trade.
    trade: dict from trades.jsonl
    resolution: "YES" or "NO" (what actually resolved)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("apis", {}).get("anthropic_key")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set. Cannot run post-mortem.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Determine if we actually lost
    won = (trade["direction"] == resolution)
    new_status = "win" if won else "loss"
    update_trade_status(trade["trade_id"], new_status)

    if won:
        log.info(f"Trade {trade['trade_id']} resolved as WIN. No post-mortem needed.")
        return

    log.info(f"Running post-mortem on loss: {trade['question'][:50]}")

    prompt = POSTMORTEM_PROMPT.format(
        question=trade["question"],
        direction=trade["direction"],
        entry_price=trade["entry_price"],
        true_prob_estimate=trade["true_prob_estimate"],
        resolution=resolution,
        edge=trade["edge"],
        confidence=trade["confidence"],
        dominant_signal=trade.get("dominant_signal", "unknown"),
        reasoning=trade.get("reasoning", "not recorded"),
        sentiment_score=trade.get("sentiment_score", "not recorded"),
        reddit_bull_ratio=trade.get("reddit_bull_ratio", "not recorded"),
        price_trend=trade.get("price_trend", "not recorded"),
        news_summary=trade.get("news_summary", "not recorded"),
    )

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        analysis = json.loads(raw)

        lesson_record = {
            "lesson_id": str(uuid.uuid4())[:8],
            "date": datetime.utcnow().isoformat(),
            "trade_id": trade["trade_id"],
            "market": trade["question"],
            "error_type": analysis.get("error_type", "UNKNOWN"),
            "what_we_thought": analysis.get("what_we_thought", ""),
            "what_happened": analysis.get("what_happened", ""),
            "lesson": analysis.get("lesson", ""),
            "signal_to_distrust": analysis.get("signal_to_distrust", "none"),
            "weight_adjustment": analysis.get("weight_adjustment", ""),
            "acceptable_loss": analysis.get("acceptable_loss", False),
        }

        LEARNINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEARNINGS_PATH, "a") as f:
            f.write(json.dumps(lesson_record) + "\n")

        log.info(f"Post-mortem complete. Error type: {lesson_record['error_type']}")
        log.info(f"Lesson: {lesson_record['lesson']}")
        return lesson_record

    except json.JSONDecodeError as e:
        log.error(f"Post-mortem JSON parse error: {e}")
    except Exception as e:
        log.error(f"Post-mortem failed: {e}")


def check_and_run_postmortems(cfg):
    """
    Check all open trades for settlement and run post-mortems as needed.
    In production this polls Polymarket for resolved markets.
    """
    trades = load_all_trades()
    open_trades = [t for t in trades if t.get("status") == "open"]

    if not open_trades:
        return

    for trade in open_trades:
        market_id = trade["market_id"]
        try:
            resp = requests.get(
                f"https://gamma-api.polymarket.com/markets/{market_id}",
                timeout=10
            )
            resp.raise_for_status()
            market = resp.json()

            if market.get("closed") or market.get("resolved"):
                resolution = "YES" if market.get("winnerOutcome") == "yes" else "NO"
                run_postmortem(trade, resolution, cfg)
        except Exception as e:
            log.debug(f"Could not check settlement for {market_id}: {e}")


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    parser = argparse.ArgumentParser()
    parser.add_argument("--market-id", help="Force post-mortem on specific trade by market ID")
    parser.add_argument("--resolution", choices=["YES", "NO"], help="What it resolved to")
    args = parser.parse_args()

    with open("config.json") as f:
        cfg = json.load(f)

    if args.market_id and args.resolution:
        trades = load_all_trades()
        trade = next((t for t in trades if t.get("market_id") == args.market_id), None)
        if trade:
            run_postmortem(trade, args.resolution, cfg)
        else:
            print(f"No trade found for market_id: {args.market_id}")
    else:
        check_and_run_postmortems(cfg)
