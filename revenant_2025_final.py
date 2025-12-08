# revenant_2025_final.py — GREEN/RED EMBEDS + TEST MODE
import os
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient
import random

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing MASSIVE_API_KEY or DISCORD_WEBHOOK_URL!")

client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','MSFT','SMCI']
CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]
ESTIMATED_HOLD = {"D":"2h – 6h", "240":"1h – 3h", "60":"30min – 1h45m", "30":"15min – 45min"}

sent_alerts = set()
premarket_done = False
last_test = 0
pst = pytz.timezone('America/Los_Angeles')

# === TEST MODE ===
TEST_MODE = True                    # ← SET TO False WHEN READY TO GO LIVE
TEST_INTERVAL = 300                 # 5 minutes

FAKE_ALERTS = [
    ("DAILY LONG NVDA", "LONG", 0x00ff00),
    ("60 SHORT TSLA", "SHORT", 0xff0000),
    ("30 LONG AMD", "LONG", 0x00ff00),
    ("4H LONG SPY", "LONG", 0x00ff00),
    ("DAILY SHORT QQQ", "SHORT", 0xff0000)
]

def now_pst():
    return datetime.now(pst)

def send_embed(title, color, fields):
    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Revenant 2025"}
    }
    payload = {"embeds": [embed]}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"{now_pst().strftime('%H:%M PST')} → {title}")
    except: print("Discord failed")

def test_mode():
    global last_test
    if time.time() - last_test >= TEST_INTERVAL:
        title, direction, color = random.choice(FAKE_ALERTS)
        fields = [
            {"name": "Entry → Target", "value": "`182.41` → `188.20` (+3.17%)", "inline": False},
            {"name": "Confluence", "value": "Confluence!" if random.random() > 0.3 else "Gamma: 185.00", "inline": True},
            {"name": "Option", "value": "185 @ $0.72" if random.random() > 0.2 else "No <$1 call", "inline": True},
            {"name": "Hold", "value": random.choice(list(ESTIMATED_HOLD.values())), "inline": True}
        ]
        send_embed(f"**TEST MODE** — {title}", color, fields)
        last_test = time.time()

# [Your full real functions here: get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live]

print("Revenant 2025 — GREEN/RED EMBEDS + TEST MODE")
while True:
    if TEST_MODE:
        test_mode()
    else:
        now = now_pst()
        if now.hour == 6 and now.minute == 20 and now.weekday() < 5:
            premarket_top5()
        if now.hour == 0 and now.minute < 5:
            premarket_done = False
            sent_alerts.clear()
        check_live()
    
    time.sleep(30 if TEST_MODE else 300)
