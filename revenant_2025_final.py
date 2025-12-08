# revenant_2025_test_mode.py
# TEST MODE ONLY — 5-minute fake alerts (zero heartbeat)
import os
import time
import requests
from datetime import datetime
import pytz
import random

# === SECRETS ===
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK:
    raise Exception("Set DISCORD_WEBHOOK_URL in GitHub/Replit secrets!")

# === TEST MODE (5-minute fake alerts) ===
TEST_MODE = True                    # ← SET TO False WHEN GOING LIVE
ALERT_EVERY_SECONDS = 300           # 5 minutes

pst = pytz.timezone('America/Los_Angeles')
last_alert = 0

FAKE_ALERTS = [
    "DAILY **LONG** NVDA\n`182.41` → `188.20` (+3.17%)\nConfluence!\n185 @ $0.72\nEstimated hold: 2h – 6h",
    "60 **SHORT** TSLA\n`454.61` → `442.10` (-2.75%)\nGamma: 450.00\n450 @ $0.68\nEstimated hold: 30min – 1h 45min",
    "30 **LONG** AMD\n`172.40` → `175.80` (+1.97%)\nConfluence!\n175 @ $0.59\nEstimated hold: 15min – 45min",
    "4H **LONG** SPY\n`685.20` → `698.50` (+1.94%)\nNo <$1 call\nEstimated hold: 1h – 3h",
    "DAILY **SHORT** QQQ\n`625.50` → `610.00` (-2.48%)\nConfluence!\n620 @ $0.81\nEstimated hold: 2h – 6h"
]

def send(text):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text})
        print(f"{datetime.now(pst).strftime('%H:%M:%S PST')} → TEST ALERT SENT")
    except:
        print("Discord failed")

print("Revenant 2025 — TEST MODE (5-min fake alerts) — NO HEARTBEAT")
while True:
    if TEST_MODE:
        if time.time() - last_alert >= ALERT_EVERY_SECONDS:
            fake = random.choice(FAKE_ALERTS)
            send(f"**TEST MODE** — {datetime.now(pst).strftime('%H:%M:%S PST')}\n{fake}")
            last_alert = time.time()
    else:
        print("TEST_MODE = False — switch to live bot")
        break
    
    time.sleep(10)
