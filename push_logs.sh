#!/bin/bash
# push_logs.sh — Commit and push latest logs to GitHub
# Run by launchd daily at 11:30am Spain time so the noon remote agent has fresh data

BOT_DIR="/Users/elysmith/polymarket-trader"
cd "$BOT_DIR"

git add logs/ && \
git commit -m "Daily log update — $(date '+%Y-%m-%d %H:%M')" && \
git push origin main

echo "Log push complete: $(date)"
