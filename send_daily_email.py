import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

subject = "Psyco Capital Bot \u2014 Daily Update 2026-04-04"

body = (
    "BOT STATUS: \U0001f7e2 Running\n"
    "\n"
    "TODAY'S ACTIVITY\n"
    "\u2022 Cycles run: ~18 (16 logged by 08:00 CEST, 2 more confirmed)\n"
    "\u2022 Markets scanned: 80+ flagged for research\n"
    "\u2022 Paper trades placed: 0\n"
    "\u2022 API spend: $0.03 / $50 limit\n"
    "\n"
    "PERFORMANCE (all-time paper)\n"
    "\u2022 Settled trades: 0 (0w / 0l)\n"
    "\u2022 Win rate: N/A \u2014 no settled trades yet\n"
    "\u2022 Net P&L: $0.00\n"
    "\u2022 Open positions: 4 ($119.71 exposure)\n"
    "\n"
    "ERRORS & ISSUES\n"
    "\u2022 CryptoPanic API key not set \u2014 404/429 warnings every cycle (non-breaking).\n"
    "  Set a real key in .env to clear the log noise.\n"
    "\u2022 No errors today \u2705\n"
    "\n"
    "STRATEGIC UPDATE\n"
    "Bot is in Phase 1 (0/50 settled trades). The hard cap is already correctly at $30. "
    "The real bottleneck: the scanner is recycling the same 5 novelty 'before GTA VI' markets "
    "every single cycle (Jesus returns, Bitcoin $1M, Rihanna album, Playboi Carti album, SCOTUS). "
    "Claude consistently rates these below the 60% confidence + 4% edge threshold, so no new trades "
    "are being placed \u2014 the 4 open positions were all placed 10 days ago. "
    "Consider lowering confidence_threshold from 0.60 to 0.55, or widening the scanner filters "
    "to surface more diverse markets. Until then the bot will keep spinning without acting."
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
