# Agent Specifications

## Agent 1: Scanner

**Trigger**: Cron every 30 minutes via run_bot.py

**Data sources**:
- Polymarket CLOB API: `GET /markets?active=true&closed=false`
- Filter: category contains "crypto" OR "finance" OR "bitcoin" OR "ethereum"

**Flagging criteria** (market must pass ALL):
- Liquidity > `scanner.min_liquidity_usd` (default $10,000)
- Volume 24h > `scanner.min_volume_24h` (default $5,000)
- Time to resolution: between 1 day and 30 days
- Spread < `scanner.max_spread_pct` (default 4%)
- Price moved > `scanner.price_move_threshold` (default 5%) in last 4 hours OR
  current YES price is between 0.15 and 0.85 (avoid near-certain outcomes)

**Output**: List of flagged market IDs passed to Agent 2

---

## Agent 2: Research (Parallel)

**Trigger**: For each flagged market from Agent 1

**Threads run concurrently**:

1. **CryptoPanic RSS** — Pull last 50 headlines tagged with relevant asset. Score sentiment -1 to +1 using keyword weighting.

2. **Reddit scrape** — Search r/CryptoCurrency, r/ethfinance, r/BitcoinMarkets for market topic. Count bullish/bearish posts in last 24h. Calculate ratio.

3. **CoinGecko price action** — Pull 7-day price chart for relevant asset. Identify: trend direction, recent spike/crash, RSI approximation.

4. **Web search** — Search for "[market question] site:bloomberg.com OR site:coindesk.com OR site:theblock.co" to get authoritative recent coverage.

**Output per market**:
```json
{
  "market_id": "...",
  "question": "...",
  "current_yes_price": 0.42,
  "sentiment_score": 0.65,
  "reddit_bull_ratio": 0.71,
  "price_trend": "up_3d",
  "news_summary": "...",
  "research_timestamp": "..."
}
```

---

## Agent 3: Calibration

**Trigger**: Receives research output from Agent 2

**Process**:
1. Load last 20 entries from `logs/learnings.jsonl` (post-mortem lessons) into context
2. Construct LLM prompt with: market question, current price, all research signals, historical lessons
3. Ask LLM: "Given all signals, what is your true probability estimate for YES? Respond with JSON: {true_prob, confidence, reasoning, dominant_signal}"
4. Calculate edge: `edge = abs(true_prob - current_yes_price)`
5. Calculate direction: BUY YES if `true_prob > current_yes_price + min_edge`, else BUY NO

**Pass to Risk agent if**:
- `confidence >= bot.confidence_threshold` (default 0.65)
- `edge >= bot.min_edge` (default 0.08 = 8 percentage points)
- Market not already in open positions

**LLM Prompt Template** (in `assets/calibration_prompt.txt`):
```
You are a prediction market calibration expert.

MARKET: {question}
CURRENT MARKET PRICE: YES={yes_price:.0%}, NO={no_price:.0%}

RESEARCH SIGNALS:
- News sentiment: {sentiment_score:.2f} (-1 bearish, +1 bullish)
- Reddit bull/bear ratio: {reddit_bull_ratio:.2f}
- Asset price trend (7d): {price_trend}
- Recent news: {news_summary}

HISTORICAL LESSONS FROM PAST TRADES:
{learnings}

Your task: Estimate the TRUE probability of YES resolving.
Be contrarian when sentiment is extreme. Weight news over Reddit.
Adjust for known biases in crypto prediction markets (tend to overprice dramatic outcomes).

Respond ONLY with valid JSON:
{
  "true_prob": 0.XX,
  "confidence": 0.XX,
  "direction": "YES" or "NO",
  "reasoning": "2-3 sentence explanation",
  "dominant_signal": "which signal drove your estimate most"
}
```

---

## Agent 4: Risk / Sizing / Execution

**Trigger**: Receives calibration output passing threshold

**Kelly Criterion sizing**:
```
kelly_fraction = (edge * (1/odds)) / (1 - current_price)
# Where edge = true_prob - market_price (for YES bet)
# Cap at risk.max_bet_fraction (default 0.25 = quarter-Kelly)
bet_usd = bankroll * kelly_fraction
bet_usd = min(bet_usd, risk.max_bet_usd_hard_cap)  # Never > $200
```

**Pre-execution checklist** (all must pass):
- [ ] `bet_usd >= risk.min_bet_usd` (default $10 — Polymarket minimum)
- [ ] `total_open_exposure + bet_usd <= bankroll * risk.max_total_exposure_fraction`
- [ ] Market still open and liquid (re-check spread)
- [ ] Not in cooldown period (3 consecutive losses triggers 6h pause)
- [ ] Dry-run mode is OFF

**Execution**:
1. Call Polymarket CLOB API: `POST /order` with calculated size
2. Wait for fill confirmation (up to 60 seconds)
3. Log to `trades.jsonl` with full reasoning chain
4. Update open positions tracker

**Trade log format**:
```json
{
  "trade_id": "uuid",
  "timestamp": "ISO8601",
  "market_id": "...",
  "question": "...",
  "direction": "YES",
  "bet_usd": 45.00,
  "entry_price": 0.38,
  "true_prob_estimate": 0.51,
  "edge": 0.13,
  "confidence": 0.71,
  "kelly_raw": 0.18,
  "kelly_applied": 0.045,
  "dominant_signal": "news_sentiment",
  "reasoning": "...",
  "status": "open"
}
```

---

## Agent 5: Post-Mortem

**Trigger**: Market settles AND our position was a loss

**Process**:
1. Load original trade record from `trades.jsonl`
2. Load research signals that were available at trade time
3. Reconstruct: what did we think, what actually happened, which signal was wrong
4. Classify error type: SENTIMENT_WRONG | TIMING_WRONG | CALIBRATION_TOO_HIGH | FALSE_EDGE | MARKET_MANIPULATION
5. Generate structured lesson

**Lesson format** (appended to `logs/learnings.jsonl`):
```json
{
  "lesson_id": "uuid",
  "date": "ISO8601",
  "market": "...",
  "error_type": "SENTIMENT_WRONG",
  "what_we_thought": "Reddit bullish + news positive → YES likely",
  "what_happened": "YES resolved 0. Price reversed on exchange hack news.",
  "lesson": "Do not weight Reddit sentiment in crypto markets when there is exchange-related risk. News latency can be 2-4h behind real events.",
  "signal_to_distrust": "reddit_bull_ratio",
  "weight_adjustment": "reduce reddit_bull_ratio weight by 30% in calibration"
}
```

**Lessons are fed back into Agent 3** on every subsequent calibration run.
