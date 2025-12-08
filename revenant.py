# revenant_2025_massive_FINAL_WORKING.py
# MASSIVE.COM API (via polygon client) + SECRETS + 6:20 AM PST
import os
import time
import requests
import yfinance as yf
from datetime import datetime
import pytz
from polygon import RESTClient   # ← THIS IS THE CORRECT IMPORT

# === SECRETS (GitHub/Replit) ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Set MASSIVE_API_KEY and DISCORD_WEBHOOK_URL in secrets!")

client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','MSFT','SMCI']
CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]

sent_alerts = set()
premarket_done = False
pst = pytz.timezone('America/Los_Angeles')

def now_pst():
    return datetime.now(pst)

# [All functions exactly as before — get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live, send]
# ... (same code you already have — just the import is fixed)

print("Revenant 2025 — MASSIVE.COM LIVE — 6:20 AM PST")
while True:
    now = now_pst()
    if now.hour == 6 and now.minute == 20 and now.weekday() < 5:
        premarket_top5()
    if now.hour == 0 and now.minute < 5:
        premarket_done = False
        sent_alerts.clear()
    check_live()
    time.sleep(300)
