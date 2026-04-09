import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

subject = "\U0001f6a8 Psyco Capital Bot \u2014 NEEDS ATTENTION 2026-04-09"

body = (
    "BOT STATUS: \U0001f534 Stopped\n"
    "Last activity: 2026-04-04 09:13 UTC (5 days ago). "
    "Final log line is 'Done for this cycle' with no subsequent Sleeping line \u2014 "
    "bot crashed at cycle end. Restart required.\n"
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
    "    \u2013 NO: Will Jesus Christ return before GTA VI? ($30)\n"
    "    \u2013 NO: Will the Detroit Pistons win the NBA Eastern Conf Finals? ($30)\n"
    "    \u2013 NO: Will Kon Knueppel win 2025-26 NBA Rookie of the Year? ($30)\n"
    "    \u2013 NO: Will bitcoin hit $1m before GTA VI? ($29.71)\n"
    "\n"
    "ERRORS & ISSUES\n"
    "\u2022 \U0001f534 CRITICAL: Bot has been down 5 days. "
    "Last log entry 2026-04-04 09:13 UTC ends without a 'Sleeping' line \u2014 "
    "bot crashed at the end of a cycle. Restart now.\n"
    "\u2022 \u26a0\ufe0f Scanner regression: now finding only ~10 crypto/finance markets out of "
    "500 fetched (was scanning all 300 broadly). Stuck recycling the same 5 stale "
    "GTA-VI-themed markets (Jesus return, Bitcoin $1M, Rihanna album, Playboi Carti, SCOTUS) "
    "every cycle \u2014 none pass confidence+edge thresholds. No new trades since 2026-03-25 (15 days).\n"
    "\u2022 \u26a0\ufe0f CryptoPanic API key not set in .env (placeholder value) \u2014 "
    "persistent 404/429 warnings every cycle. Non-breaking but add a real key to fix.\n"
    "\n"
    "STRATEGIC UPDATE\n"
    "Still Phase 1 (0/50 settled trades). Three things need fixing after restart: "
    "(1) Restart the bot \u2014 crashed 5 days ago. "
    "(2) The scanner filter changed and is now too narrow \u2014 only 10 markets flagged per "
    "500 fetched, all low-confidence novelty bets. Broaden the scanner category filters "
    "back to the original behaviour or lower confidence_threshold from 0.60 to 0.55. "
    "(3) The hard cap is already correctly set at $30 \u2014 no change needed there."
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
