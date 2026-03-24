---
name: polymarket-crypto-trader
description: Autonomous Polymarket + Kalshi prediction market trading bot for crypto/finance markets. Use this skill whenever the user asks to run, start, stop, check, configure, or review the trading bot. Also triggers for: open positions, post-mortems, Kelly sizing, Brier Score, Sharpe ratio, performance metrics, scanning markets, adding new AI models, kill switch, or any Polymarket/Kalshi trading workflow. Orchestrates a 5-agent pipeline with multi-model consensus voting and deterministic risk validation.
---

# Polymarket + Kalshi Crypto Trading Bot

## Architecture Overview

```
Scanner → Research (parallel) → Calibration (multi-model vote) → Risk/Sizing → Execution
                                                                         ↓
                                                          Post-Mortem (on every loss)
```

**Two exchanges**: Polymarket (crypto-native, Polygon) + Kalshi (US-regulated, cash-settled)  
**Five AI models**: Claude, GPT-4o, Gemini, DeepSeek, Grok — start with Claude, add others over time  
**All risk checks run in Python** (validate_risk.py), not language instructions — deterministic

---

## Quick Commands

| What you want | Command |
|---|---|
| Start bot (dry run) | `python scripts/run_bot.py --mode dry` |
| Start bot (live) | `python scripts/run_bot.py --mode live` |
| One test cycle | `python scripts/run_bot.py --mode dry --once` |
| Check open positions | `python scripts/review.py --status` |
| Performance metrics | `python scripts/metrics.py` |
| Full trade breakdown | `python scripts/metrics.py --full` |
| Today's trades | `python scripts/review.py --today` |
| Test risk math | `python scripts/validate_risk.py` |
| Test Kelly sizing | `python scripts/kelly_size.py` |
| Force post-mortem | `python scripts/postmortem.py --market-id <id> --resolution YES` |
| **Emergency stop** | `touch STOP` (creates kill switch file) |
| **Resume after stop** | `rm STOP` |
| Stop daemon | `launchctl unload ~/Library/LaunchAgents/com.psyco.polytrader.plist` |
| Start daemon | `launchctl load ~/Library/LaunchAgents/com.psyco.polytrader.plist` |
| Watch live logs | `tail -f logs/bot.log` |

---

## Configuration (config.json)

**Critical settings to set before going live:**
- `risk.bankroll_usd` — your actual USDC balance
- `risk.max_bet_usd_hard_cap` — never bet more than this per trade (default: $37 = 5% of $750)
- `bot.initial_dry_run_hours` — mandatory dry run period (default: 48h)
- `scanner.exchanges` — which exchanges to scan: `["polymarket"]` or `["polymarket", "kalshi"]`

**Risk limits (do not raise these on a $500-2K bankroll):**
- Max single position: 5% of bankroll
- Max total exposure: 15% of bankroll at once
- Max concurrent positions: 15
- Max drawdown before full stop: 8%
- Daily loss limit: 15%
- Daily API cost cap: $50

**Adding AI models** — toggle in config.json `prediction.models`:
```json
"gpt4o": { "enabled": true, "weight": 0.20, "role": "bull_advocate" }
```
Then add the corresponding API key to `.env`.

---

## Safety Systems

1. **Kill switch** — `touch STOP` in bot directory halts all new trades immediately
2. **48h dry run lockout** — no real trades for first 2 days, regardless of mode flag
3. **Drawdown circuit breaker** — stops trading if account drops 8% from peak
4. **Daily loss limit** — auto-stops at 15% daily loss
5. **VaR check** — each bet's 95% confidence loss must stay under 5% of bankroll
6. **API cost cap** — halts calibration calls if daily API spend hits $50
7. **Conflicted models** — if AI models disagree by >15 percentage points, trade is blocked
8. **Slippage abort** — if price moves >2% between signal and fill, order is cancelled

---

## Performance Targets (from config.json)

| Metric | Target | What it means |
|---|---|---|
| Win Rate | ≥ 60% | % of trades that profit |
| Sharpe Ratio | ≥ 2.0 | Risk-adjusted return |
| Profit Factor | ≥ 1.5 | Gross profit / gross loss |
| Brier Score | < 0.25 | Calibration quality (lower = better) |
| Max Drawdown | < 8% | Peak-to-trough decline before pause |

Check these weekly with `python scripts/metrics.py`. If Brier Score climbs above 0.25,
the model is miscalibrating — review learnings.jsonl and adjust confidence threshold.

---

## File Map

```
polymarket-trader/
├── SKILL.md                     ← You are here
├── config.json                  ← All tunable parameters
├── .env                         ← Secrets (never commit)
├── STOP                         ← Kill switch (create to halt, delete to resume)
├── scripts/
│   ├── run_bot.py               ← Main orchestrator loop
│   ├── scanner.py               ← Agent 1: market scanner (Polymarket + Kalshi)
│   ├── research.py              ← Agent 2: parallel research
│   ├── calibrate.py             ← Agent 3: multi-model consensus voting
│   ├── validate_risk.py         ← Deterministic risk checks (Python, not language)
│   ├── kelly_size.py            ← Kelly Criterion + VaR calculator
│   ├── risk.py                  ← Agent 4: calls validate + kelly, executes orders
│   ├── postmortem.py            ← Agent 5: loss analysis + lessons
│   ├── metrics.py               ← Performance dashboard
│   └── review.py                ← Position viewer + daily summary
├── references/
│   ├── agent-specs.md           ← Detailed agent logic
│   ├── platforms.md             ← Polymarket + Kalshi API reference
│   └── formulas.md              ← All math: Kelly, Brier, Sharpe, VaR
├── logs/
│   ├── trades.jsonl             ← All trade records
│   ├── learnings.jsonl          ← Post-mortem lessons
│   ├── api_costs.jsonl          ← Daily API spend tracking
│   └── bot.log                  ← Runtime logs
└── assets/
    └── com.psyco.polytrader.plist  ← macOS daemon
```

---

## Troubleshooting

**No trades after 24h dry run**: Normal. Crypto/finance markets are competitive. 
Check `logs/bot.log` — look for "FAIL" lines to see what's being filtered out.
Try lowering `bot.confidence_threshold` to 0.60 temporarily to see near-misses.

**Brier Score above 0.25**: Model is overconfident. Review `logs/learnings.jsonl` 
for patterns. Consider lowering `bot.min_edge` to reduce threshold for trading.

**Models conflicted**: Two or more AI models disagree by >15%. This is a feature — 
it blocks trades where there's no consensus. Review research signals manually.

**Kill switch won't clear**: Make sure you're deleting the file named exactly `STOP` 
(no extension) in the bot root directory: `rm ~/polymarket-trader/STOP`

**Kalshi orders failing**: Use demo environment first. Check `KALSHI_API_KEY` is set. 
Kalshi requires a signed developer agreement before live trading.

**API costs too high**: Reduce `scanner.max_markets_per_cycle` or increase 
`bot.cycle_seconds`. Each market researched costs ~$0.003 in Claude API calls.
