import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

subject = "\U0001f6a8 Psyco Capital Bot \u2014 NEEDS ATTENTION 2026-04-10"

body = (
    "BOT STATUS: \U0001f534 Stopped\n"
    "Last activity: 2026-04-04 09:13 UTC (6 days ago). "
    "Final log line is 'Sleeping 1800s until next cycle' \u2014 "
    "bot went to sleep and never woke up. Restart required.\n"
    "\n"
    "TODAY'S ACTIVITY\n"
    "\u2022 Cycles run: 0 (bot stopped)\n"
    "\u2022 Markets scanned: 0\n"
    "\u2022 Paper trades placed: 0\n"
    "\u2022 API spend: $0.00 / $50 limit\n"
    "\n"
    "PERFORMANCE (all-time paper)\n"
    "\u2022 Settled trades: 0 (0w / 0l)\n"
    "\u2022 Win rate: N/A \u2014 no settled trades yet\n"
    "\u2022 Net P&L: $0.00\n"
    "\u2022 Open positions: 4 ($119.71 exposure)\n"
    "    \u2013 NO: Will Jesus Christ return before GTA VI? ($30.00)\n"
    "    \u2013 NO: Will the Detroit Pistons win the NBA Eastern Conf Finals? ($30.00)\n"
    "    \u2013 NO: Will Kon Knueppel win 2025-26 NBA Rookie of the Year? ($30.00)\n"
    "    \u2013 NO: Will bitcoin hit $1m before GTA VI? ($29.71)\n"
    "\n"
    "ERRORS & ISSUES\n"
    "\u2022 \U0001f534 CRITICAL: Bot has been down 6 days. "
    "Last log entry 2026-04-04 09:13 UTC \u2014 "
    "bot entered sleep cycle and never restarted. Restart now with run_bot_daemon.sh.\n"
    "\u2022 \u26a0\ufe0f Scanner stuck on stale markets: only ~10 crypto/finance markets found "
    "per 500 fetched, all recycling the same 5 GTA-VI-themed novelty bets "
    "(Jesus return, Bitcoin $1M, Rihanna album, Playboi Carti, SCOTUS). "
    "None pass confidence+edge thresholds. No new trades placed since 2026-03-25 (16 days ago).\n"
    "\u2022 \u26a0\ufe0f CryptoPanic API key not configured in .env (placeholder value) \u2014 "
    "persistent 404/429 errors every cycle. Non-breaking but set a real key.\n"
    "\n"
    "STRATEGIC UPDATE\n"
    "Still Phase 1 (0/50 settled trades \u2014 no data yet). Two urgent fixes after restart: "
    "(1) Restart the bot \u2014 it has been dead for 6 days, likely a process manager issue. "
    "Check run_bot_daemon.sh and consider a cron job or systemd service so it auto-restarts. "
    "(2) The scanner category filter is too narrow \u2014 consider lowering confidence_threshold "
    "from 0.60 to 0.55 or broadening scanner filters to surface fresh markets beyond the same "
    "5 stale bets. The hard cap is correctly set at $30 \u2014 no change needed there."
)

msg = MIMEMultipart()
msg['From'] = 'psycobot@localhost'
msg['To'] = 'crew@psycoskateboards.com'
msg['Subject'] = subject
msg.attach(MIMEText(body, 'plain'))

try:
    with smtplib.SMTP('localhost', 25, timeout=5) as s:
        s.sendmail('psycobot@localhost', ['crew@psycoskateboards.com'], msg.as_string())
    print('EMAIL SENT OK')
except Exception as e:
    print(f'SMTP FAILED: {e}')
    print()
    print('--- EMAIL DRAFT (copy/send manually) ---')
    print(f'To: crew@psycoskateboards.com')
    print(f'Subject: {subject}')
    print()
    print(body)
