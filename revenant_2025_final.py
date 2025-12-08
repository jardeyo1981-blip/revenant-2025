# revenant_2025_final_PERFECT.py
# EXACTLY LIKE YOUR PHOTO — NO HEARTBEAT — TEST MODE CLEAN
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
    raise Exception("Missing secrets!")

client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','MSFT','SMCI']
CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]
ESTIMATED_HOLD = {"D":"2h – 6h", "240":"1h – 3h", "60":"30min – 1h45m", "30":"15min – 45min"}

sent_alerts = set()
premarket_done = False
last_test_alert = 0
TEST_MODE = True                    # ← SET TO False TO GO LIVE
pst = pytz.timezone('America/Los_Angeles')

def now_pst():
    return datetime.now(pst)

def send(text):
    payload = {"content": text}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"{now_pst().strftime('%H:%M PST')} → Alert sent")
    except:
        print("Discord failed")

# TEST MODE — Every 5 minutes, exact photo format
def test_mode():
    global last_test_alert
    if time.time() - last_test_alert < 300:
        return
    last_test_alert = time.time()

    examples = [
        "TEST MODE — 4H LONG SPY\n\n**Entry → Target**\n`182.41` → `188.20` (+3.17%)\n\n**Confluence**\nGamma: 185.00\n\n**Option**\n185 @ $0.72\n\n**Hold**\n30min – 1h45m",
        "TEST MODE — DAILY LONG NVDA\n\n**Entry → Target**\n`182.41` → `188.20` (+3.17%)\n\n**Confluence**\nConfluence!\n\n**Option**\n185 @ $0.72\n\n**Hold**\n2h – 6h",
        "TEST MODE — 60 SHORT TSLA\n\n**Entry → Target**\n`454.61` → `442.10` (-2.75%)\n\n**Confluence**\nGamma: 450.00\n\n**Option**\n450 @ $0.68\n\n**Hold**\n30min – 1h45m"
    ]
    send(random.choice(examples))

# REAL ALERT FORMAT — EXACTLY LIKE YOUR PHOTO
def send_live_alert(direction, ticker, tf, price, target, gap_pct, conf, opt, hold):
    title = f"{'DAILY' if tf=='D' else tf} {direction} {ticker}"
    msg = f"{title}\n\n" \
          f"**Entry → Target**\n" \
          f"`{price:.2f}` → `{target:.2f}` ({'+' if direction=='LONG' else '-'}{gap_pct:.2f}%)\n\n" \
          f"**Confluence**\n{conf}\n\n" \
          f"**Option**\n{opt}\n\n" \
          f"**Hold**\n{hold}"
    send(msg)

# [Your full get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live functions here]
# Inside check_live() — replace send() calls with send_live_alert()

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
