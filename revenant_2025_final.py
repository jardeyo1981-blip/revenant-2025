# revenant_2025_SEXY_FINAL.py
# GREEN LONG / RED SHORT + EMOJIS + TEST MODE (2-min alerts + fake pre-market)
import os
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz
from polygon import RESTClient
import random

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing secrets!")

client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','TSLA','NVDA','AAPL','AMD','MSFT','AMZN','META','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]
ESTIMATED_HOLD = {"D":"2h – 6h", "240":"1h – 3h", "60":"30min – 1h45m", "30":"15min – 45min"}

sent_alerts = set()
last_test = 0
premarket_sent = False
TEST_MODE = True                    # ← SET TO False TO GO LIVE
TEST_INTERVAL = 120                 # 2 minutes

pst = pytz.timezone('America/Los_Angeles')

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

# TEST MODE — 2-minute fake alerts + fake pre-market
def test_mode():
    global last_test, premarket_sent
    if time.time() - last_test < TEST_INTERVAL:
        return
    last_test = time.time()

    # Fake pre-market at startup
    if not premarket_sent:
        send("**6:20 AM PST — PRE-MARKET TOP 5**\n\n"
             "1. NVDA → DAILY `188.20` (**+4.2%**) 🌙\n"
             "2. TSLA → 4H `442.10` (**-3.1%**) 🔥\n"
             "3. SMCI → 1H `445.60` (**+3.8%**) 🚀\n"
             "4. SPY → DAILY `698.50` (**+2.1%**) 💵\n"
             "5. QQQ → 1H `188.20` (**+2.9%**) ⭐")
        premarket_sent = True

    # Rotating fake alerts
    examples = [
        ("DAILY LONG NVDA 🌙", 0x00ff00, "185 @ $0.52", "+$1,248 (+240%)", "2h – 6h"),
        ("60 SHORT TSLA 🔥", 0xff0000, "450 @ $0.68", "+$962 (+141%)", "30min – 1h45m"),
        ("30 LONG AMD 🚀", 0x00ff00, "175 @ $0.59", "+$1,020 (+173%)", "15min – 45min"),
        ("4H LONG SPY 💵", 0x00ff00, "690 @ $0.78", "+$1,456 (+187%)", "1h – 3h"),
        ("DAILY SHORT QQQ ⭐", 0xff0000, "620 @ $0.81", "+$1,134 (+140%)", "2h – 6h")
    ]
    title, color, opt, profit, hold = random.choice(examples)
    fields = [
        {"name": "Entry → Target", "value": "`182.41` → `188.20` (+3.17%)", "inline": False},
        {"name": "Gamma Flip", "value": "Confluence!", "inline": True},
        {"name": "Contract", "value": opt, "inline": True},
        {"name": "Profit if target hit", "value": profit, "inline": False},
        {"name": "Hold", "value": hold, "inline": True}
    ]
    send_embed(title, color, fields)

# [All your real functions here — get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live]

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
