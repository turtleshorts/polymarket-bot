# Core Formulas Reference

All math used by the bot. Source: guide + Kelly Criterion literature.

---

## Edge Detection

**Expected Value**
```
EV = p * b - (1 - p)
p = your model's true probability
b = decimal odds - 1  (what you win per $1 bet)
```

**Market Edge**
```
edge = p_model - p_market
Trade only when edge > 0.04 (4 percentage points)
```

**Mispricing Score (Z-score)**
```
S = (p_model - p_market) / sigma
sigma = standard deviation of model predictions
Higher S = stronger signal
```

---

## Position Sizing

**Full Kelly Criterion**
```
f* = (p * b - q) / b
p = win probability
q = 1 - p (loss probability)
b = net odds (payout per $1 risked)
```

**Fractional Kelly**
```
f = f* * alpha
alpha = 0.25 for quarter-Kelly (recommended)
alpha = 0.50 for half-Kelly
```
Most professional traders use quarter-Kelly. Full Kelly is mathematically optimal
but produces extreme variance — one bad run can wipe you out.

**Example**:
- Bankroll: $1,000
- Win probability: 70%
- Odds: 2:1 (b = 1.0)
- Full Kelly: (0.70 * 1.0 - 0.30) / 1.0 = 0.40 → bet $400
- Quarter-Kelly: 0.40 * 0.25 = 0.10 → bet $100 ✅

---

## Risk Management

**Value at Risk (95% confidence)**
```
VaR = bet_usd * 1.645
1.645 = z-score for 95% confidence interval
Max daily VaR = bankroll * 0.05 (5%)
```

**Max Drawdown**
```
MDD = (Peak - Trough) / Peak
Block new trades if MDD > 8%
```

**Daily Loss Limit**
```
Stop trading if daily_loss > bankroll * 0.15 (15%)
```

---

## Performance Metrics

**Win Rate**
```
Win Rate = wins / total_settled_trades
Target: >= 60%
```

**Sharpe Ratio**
```
SR = (mean_return - risk_free_rate) / std_return
mean_return = average P&L per trade as fraction of bankroll
risk_free_rate = 0 (approximation)
Target: >= 2.0
```

**Profit Factor**
```
PF = gross_profit / gross_loss
gross_profit = sum of all winning trade profits
gross_loss = sum of all losing trade losses (absolute value)
Target: >= 1.5
```

**Brier Score (Calibration)**
```
BS = (1/n) * sum((predicted_prob - actual_outcome)^2)
actual_outcome = 1 if we won, 0 if we lost
Target: < 0.25 (lower is better)
```
A well-calibrated model: when you say 70% probability, it should happen ~70% of the time.
Track this over 50+ trades to get a meaningful signal.

---

## Bayesian Update (Optional Enhancement)

```
P(H|E) = P(E|H) * P(H) / P(E)
H = hypothesis (YES resolves)
E = evidence (new signal)
```
Update probability with each new signal rather than re-running full calibration.
Useful for monitoring open positions as new information arrives.

---

## Arbitrage Condition

```
Sum(1/odds_i) < 1 = profit opportunity
If YES_price + NO_price < 1.00 = buy both sides for guaranteed profit
Common on thin markets but rare on liquid ones
```
