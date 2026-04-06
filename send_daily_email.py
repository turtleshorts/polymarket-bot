import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

subject = "\U0001f6a8 Psyco Capital Bot \u2014 NEEDS ATTENTION 2026-04-06"

body = (
    "BOT STATUS: \U0001f534 Stopped\n"
    "Last activity: 2026-04-04 09:13 CEST (~51 hours ago). "
    "Bot entered a 30-min sleep and never resumed. Needs restart.\n"
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
    "\n"
    "ERRORS & ISSUES\n"
    "\u2022 \U0001f534 CRITICAL: Bot has been down ~51 hours. "
    "Last log line: '2026-04-04 09:13 Sleeping 1800s' \u2014 never woke up. Restart required.\n"
    "\u2022 \u26a0\ufe0f CryptoPanic API key not set \u2014 persistent 404/429 warnings every cycle (non-breaking but noisy). "
    "Set a real key in .env to fix.\n"
    "\u2022 \u26a0\ufe0f Scanner is now filtering to crypto/finance only (~10 markets from 500 fetched). "
    "It keeps cycling the same 5 stale GTA VI markets (Jesus returns, Bitcoin $1M, Rihanna, Carti, SCOTUS) "
    "\u2014 none pass confidence+edge. No new trades since 2026-03-25.\n"
    "\n"
    "STRATEGIC UPDATE\n"
    "Phase 1 (0/50 settled trades). Priority #1: restart the bot. "
    "Once running again, the scanner filter may be too narrow \u2014 it's only surfacing 5 recycled markets "
    "and passing zero to execution. Consider lowering confidence_threshold from 0.60 to 0.55 or "
    "broadening scanner filters (e.g. re-enabling non-crypto markets) to get more diverse opportunities "
    "and start accumulating settled trade data."
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
