#!/bin/bash
# Wrapper script for launchd — ensures PYTHONPATH is set correctly.
# Called by com.psyco.polytrader.plist. DO NOT run with --mode live.

BOT_DIR="/Users/elysmith/polymarket-trader"
cd "$BOT_DIR"
export PYTHONPATH="$BOT_DIR"

exec "$BOT_DIR/venv/bin/python" scripts/run_bot.py --mode dry
