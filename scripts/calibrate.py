#!/usr/bin/env python3
"""
Agent 3: Probability Calibration — Multi-Model Consensus
Each enabled model votes independently with a weighted role.

Model roster (from the guide):
  Grok         30% — primary forecaster        (set GROK_API_KEY in .env)
  Claude       20% — news analyst              (ANTHROPIC_API_KEY)
  GPT-4o       20% — bull case advocate        (OPENAI_API_KEY)
  Gemini Flash 15% — bear case advocate        (GOOGLE_API_KEY)
  DeepSeek     15% — risk manager              (DEEPSEEK_API_KEY)

Start with just Claude enabled. Toggle others in config.json -> prediction.models.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic

log = logging.getLogger("polybot.calibrate")

ROOT = Path(__file__).parent.parent
LEARNINGS_PATH = ROOT / "logs" / "learnings.jsonl"
API_COSTS_PATH = ROOT / "logs" / "api_costs.jsonl"

COST_PER_CALL_USD = 0.003


def build_prompt(market, role, learnings_text):
    yes_price = market["yes_price"]
    no_price = round(1 - yes_price, 4)

    role_instructions = {
        "news_analyst": "Focus primarily on news and information signals. Weight recent headlines heavily.",
        "primary_forecaster": "Make your best overall probability estimate using all available signals.",
        "bull_advocate": "Argue the bull case. What would make YES resolve? Push your estimate bullish if there is any reasonable case.",
        "bear_advocate": "Argue the bear case. What would make NO resolve? Push your estimate bearish if there is any reasonable case.",
        "risk_manager": "Be conservative. Identify the main risks. Default toward the market price unless signals are very strong.",
    }

    return f"""You are a prediction market calibration expert. Your specific role: {role_instructions.get(role, 'primary_forecaster')}

MARKET QUESTION: {market['question']}
CURRENT MARKET PRICE: YES={yes_price:.0%}, NO={no_price:.0%}
DAYS UNTIL RESOLUTION: {market.get('resolution_days', 'unknown')}

RESEARCH SIGNALS:
- News sentiment score: {market.get('sentiment_score', 0):.2f} (-1.0 bearish, +1.0 bullish)
- Reddit bull/bear ratio: {market.get('reddit_bull_ratio', 0.5):.2f}
- Asset price trend (7 days): {market.get('price_trend', 'unknown')}
- Recent headlines: {market.get('news_summary', 'No data')}

LESSONS FROM PREVIOUS LOSING TRADES:
{learnings_text}

CALIBRATION RULES:
1. Market price is your base rate
2. Only move away if signals are STRONG and directional
3. Reddit in crypto is often contrarian — be skeptical
4. Weight news over social sentiment
5. Crypto markets overprice dramatic outcomes
6. Apply past lessons — distrust signals that have failed before

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "true_prob": 0.XX,
  "confidence": 0.XX,
  "direction": "YES",
  "reasoning": "2-3 sentence explanation",
  "dominant_signal": "news_sentiment OR reddit OR price_trend OR market_price OR lessons",
  "signal_agreement": "aligned OR mixed OR conflicted"
}}"""


def load_recent_learnings(n=20):
    learnings = []
    if not LEARNINGS_PATH.exists():
        return []
    with open(LEARNINGS_PATH) as f:
        for line in f:
            try:
                learnings.append(json.loads(line))
            except Exception:
                pass
    return learnings[-n:]


def format_learnings(learnings):
    if not learnings:
        return "No historical losses yet."
    lines = []
    for l in learnings[-5:]:
        lines.append(
            f"- [{l.get('error_type', 'UNKNOWN')}] {l.get('lesson', '')} "
            f"(Distrust: {l.get('signal_to_distrust', 'none')})"
        )
    return "\n".join(lines)


def log_api_cost(model_name, cost_usd):
    API_COSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(API_COSTS_PATH, "a") as f:
        f.write(json.dumps({
            "date": datetime.utcnow().date().isoformat(),
            "timestamp": datetime.utcnow().isoformat(),
            "model": model_name,
            "cost_usd": cost_usd,
        }) + "\n")


def call_claude(prompt, role):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match: raw = match.group(0)
        result = json.loads(raw)
        log_api_cost("claude", COST_PER_CALL_USD)
        return result
    except Exception as e:
        log.error(f"Claude call failed: {e}")
        return None


def call_openai(prompt, role):
    try:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        log_api_cost("gpt4o", 0.005)
        return result
    except ImportError:
        log.debug("openai package not installed")
        return None
    except Exception as e:
        log.error(f"GPT-4o call failed: {e}")
        return None


def call_gemini(prompt, role):
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        result = json.loads(response.text.strip())
        log_api_cost("gemini", 0.001)
        return result
    except ImportError:
        log.debug("google-generativeai not installed")
        return None
    except Exception as e:
        log.error(f"Gemini call failed: {e}")
        return None


def call_deepseek(prompt, role):
    try:
        import openai
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            return None
        client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat", max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.choices[0].message.content.strip())
        log_api_cost("deepseek", 0.001)
        return result
    except ImportError:
        log.debug("openai package not installed (needed for DeepSeek)")
        return None
    except Exception as e:
        log.error(f"DeepSeek call failed: {e}")
        return None


MODEL_CALLERS = {
    "claude":    call_claude,
    "gpt4o":     call_openai,
    "gemini":    call_gemini,
    "deepseek":  call_deepseek,
}


def aggregate_votes(votes):
    if not votes:
        return None
    total_weight = sum(v["weight"] for v in votes)
    weighted_prob = sum(v["true_prob"] * v["weight"] for v in votes) / total_weight
    weighted_conf = sum(v["confidence"] * v["weight"] for v in votes) / total_weight

    probs = [v["true_prob"] for v in votes]
    spread = max(probs) - min(probs)
    if spread > 0.15:
        signal_agreement = "conflicted"
    elif spread > 0.08:
        signal_agreement = "mixed"
    else:
        signal_agreement = "aligned"

    direction = "YES" if weighted_prob > 0.50 else "NO"
    model_summary = ", ".join(
        f"{v['model']}={v['true_prob']:.0%}" for v in votes
    )

    return {
        "true_prob": round(weighted_prob, 4),
        "confidence": round(weighted_conf, 4),
        "direction": direction,
        "signal_agreement": signal_agreement,
        "model_spread": round(spread, 4),
        "votes": votes,
        "reasoning": f"Consensus ({len(votes)} model(s)): {model_summary}",
        "dominant_signal": votes[0]["dominant_signal"] if votes else "unknown",
    }


def calibrate_one(market, cfg):
    learnings = load_recent_learnings()
    learnings_text = format_learnings(learnings)
    prediction_cfg = cfg.get("prediction", {}).get("models", {})

    votes = []
    for model_name, model_cfg in prediction_cfg.items():
        if not model_cfg.get("enabled", False):
            continue
        role = model_cfg.get("role", "primary_forecaster")
        weight = model_cfg.get("weight", 0.20)
        caller = MODEL_CALLERS.get(model_name)
        if not caller:
            continue

        prompt = build_prompt(market, role, learnings_text)
        result = caller(prompt, role)

        if result and "true_prob" in result:
            votes.append({
                "model": model_name,
                "role": role,
                "weight": weight,
                "true_prob": float(result["true_prob"]),
                "confidence": float(result.get("confidence", 0.5)),
                "direction": result.get("direction", "YES"),
                "reasoning": result.get("reasoning", ""),
                "dominant_signal": result.get("dominant_signal", "unknown"),
                "signal_agreement": result.get("signal_agreement", "unknown"),
            })

    if not votes:
        log.error("No model votes received")
        return {**market, "passes_threshold": False, "error": "no_votes"}

    consensus = aggregate_votes(votes)
    yes_price = market["yes_price"]
    direction = consensus["direction"]
    true_prob = consensus["true_prob"]

    edge = (true_prob - yes_price) if direction == "YES" else ((1 - true_prob) - (1 - yes_price))

    min_edge = cfg["bot"]["min_edge"]
    min_conf = cfg["bot"]["confidence_threshold"]
    passes = (consensus["confidence"] >= min_conf) and (edge >= min_edge)

    # Block if models are conflicted — not enough consensus to trade
    if consensus["signal_agreement"] == "conflicted":
        passes = False

    return {
        **market,
        "calibration": consensus,
        "true_prob": true_prob,
        "direction": direction,
        "confidence": consensus["confidence"],
        "edge": round(edge, 4),
        "model_votes": votes,
        "signal_agreement": consensus["signal_agreement"],
        "passes_threshold": passes,
        "calibrated_at": datetime.utcnow().isoformat(),
    }


def run_calibration(research_results, cfg):
    calibrated = []
    for market in research_results:
        result = calibrate_one(market, cfg)
        status = "PASS" if result["passes_threshold"] else "FAIL"
        log.info(
            f"  [{status}] {market['question'][:50]} | "
            f"edge={result.get('edge', 0):.2%} "
            f"conf={result.get('confidence', 0):.0%} "
            f"models={len(result.get('model_votes', []))}"
        )
        calibrated.append(result)
    return calibrated


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    with open(ROOT / "config.json") as f:
        cfg = json.load(f)
    test = [{
        "market_id": "test",
        "question": "Will Bitcoin exceed $100k by end of March?",
        "yes_price": 0.28, "resolution_days": 12, "liquidity": 50000,
        "volume_24h": 12000, "tags": [],
        "scanned_at": datetime.utcnow().isoformat(),
        "sentiment_score": 0.4, "reddit_bull_ratio": 0.6,
        "price_trend": "up",
        "news_summary": "Bitcoin rally continues as ETF inflows rise",
        "asset": "bitcoin",
        "researched_at": datetime.utcnow().isoformat(),
    }]
    results = run_calibration(test, cfg)
    print(json.dumps(results, indent=2, default=str))
