#!/usr/bin/env python3
"""
Polymarket Crypto Trading Bot — Main Orchestrator
Psyco Capital / run_bot.py

Runs the 5-agent pipeline on a 30-minute cycle.
Usage:
  python scripts/run_bot.py --mode dry    # No real trades
  python scripts/run_bot.py --mode live   # Real trades (requires wallet + API key)
"""

import argparse
from dotenv import load_dotenv
load_dotenv()
import json
import logging
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- Setup ---
ROOT = Path(__file__).parent.parent
LOG_PATH = ROOT / "logs" / "bot.log"
TRADES_PATH = ROOT / "logs" / "trades.jsonl"
CONFIG_PATH = ROOT / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("polybot")


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    return cfg


def load_open_positions():
    """Return list of open trades from trades.jsonl."""
    positions = []
    if TRADES_PATH.exists():
        with open(TRADES_PATH) as f:
            for line in f:
                t = json.loads(line)
                if t.get("status") == "open":
                    positions.append(t)
    return positions


def check_consecutive_losses(n=3):
    """Return True if last n settled trades were all losses."""
    settled = []
    if TRADES_PATH.exists():
        with open(TRADES_PATH) as f:
            for line in f:
                t = json.loads(line)
                if t.get("status") in ("win", "loss"):
                    settled.append(t)
    if len(settled) < n:
        return False
    return all(t["status"] == "loss" for t in settled[-n:])


def run_cycle(cfg, mode):
    """Execute one full scan → research → calibrate → risk → execute cycle."""
    from scripts.scanner import run_scanner
    from scripts.research import run_research
    from scripts.calibrate import run_calibration
    from scripts.risk import run_risk_and_execute

    log.info(f"=== Cycle start | mode={mode} | {datetime.utcnow().isoformat()} ===")

    # Safety check: consecutive loss cooldown
    if check_consecutive_losses(n=cfg["bot"]["consecutive_loss_pause_count"]):
        log.warning("3 consecutive losses detected. Pausing for 6 hours.")
        time.sleep(cfg["bot"]["loss_cooldown_seconds"])
        return

    # Agent 1: Scan
    log.info("Agent 1: Scanning markets...")
    flagged_markets = run_scanner(cfg)
    log.info(f"  → {len(flagged_markets)} markets flagged")

    if not flagged_markets:
        log.info("No markets flagged. Sleeping until next cycle.")
        return

    # Agent 2: Research (parallel)
    log.info("Agent 2: Running parallel research...")
    research_results = run_research(flagged_markets, cfg)
    log.info(f"  → Research complete on {len(research_results)} markets")

    # Agent 3: Calibration
    log.info("Agent 3: Calibrating probabilities...")
    calibrated = run_calibration(research_results, cfg)
    passing = [c for c in calibrated if c["passes_threshold"]]
    log.info(f"  → {len(passing)}/{len(calibrated)} markets passed confidence threshold")

    if not passing:
        log.info("No markets passed calibration. Done for this cycle.")
        return

    # Agent 4: Risk + Execution
    open_positions = load_open_positions()
    log.info(f"Agent 4: Risk/sizing ({len(open_positions)} currently open)...")
    for opportunity in passing:
        run_risk_and_execute(opportunity, open_positions, cfg, mode=mode)

    log.info("=== Cycle complete ===\n")


def main():
    parser = argparse.ArgumentParser(description="Polymarket Trading Bot")
    parser.add_argument("--mode", choices=["live", "dry"], default="dry",
                        help="live = real trades, dry = simulate only")
    parser.add_argument("--once", action="store_true",
                        help="Run one cycle then exit (useful for testing)")
    args = parser.parse_args()

    cfg = load_config()

    # Force dry run during initial lockout period
    if cfg["bot"].get("initial_dry_run_hours", 0) > 0:
        bot_start_file = ROOT / "logs" / ".bot_first_run"
        if not bot_start_file.exists():
            bot_start_file.write_text(datetime.utcnow().isoformat())

        first_run = datetime.fromisoformat(bot_start_file.read_text().strip())
        lockout_end = first_run + timedelta(hours=cfg["bot"]["initial_dry_run_hours"])
        if datetime.utcnow() < lockout_end:
            remaining = (lockout_end - datetime.utcnow()).seconds // 3600
            log.warning(f"Initial dry-run lockout active. {remaining}h remaining. Forcing dry mode.")
            args.mode = "dry"

    log.info(f"Polymarket Bot starting | mode={args.mode} | cycle={cfg['bot']['cycle_seconds']}s")

    while True:
        try:
            run_cycle(cfg, mode=args.mode)
        except KeyboardInterrupt:
            log.info("Shutdown requested. Exiting.")
            sys.exit(0)
        except Exception as e:
            log.error(f"Cycle error: {e}", exc_info=True)
            log.info("Sleeping 5 minutes before retry...")
            time.sleep(300)
            continue

        if args.once:
            log.info("--once flag set. Exiting after single cycle.")
            break

        log.info(f"Sleeping {cfg['bot']['cycle_seconds']}s until next cycle...")
        time.sleep(cfg["bot"]["cycle_seconds"])


if __name__ == "__main__":
    main()
