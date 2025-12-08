# revenant_2025_final_MAX_PERCENT_ONLY.py
# LIVE — DAILY POST-MORTEM WITH MAX % GAIN + TOTAL % (NO $)
import os
import time
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

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
daily_trades = []        # Stores: ticker, direction, tf, profit_pct
premarket_done = False
last_daily_report = None
pst = pytz.timezone('America/Los_Angeles')

def now_pst():
    return datetime.now(pst)

def send(text):
    payload = {"content": text}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"{now_pst().strftime('%H:%M PST')} → Sent")
    except: print("Discord failed")

# [All your existing functions unchanged: get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live]

# Inside check_live() — when a trade triggers:
def record_trade(ticker, direction, tf, profit_pct):
    daily_trades.append({
        "ticker": ticker,
        "direction": direction,
        "tf": "DAILY" if tf=="D" else tf,
        "profit_pct": profit_pct
    })

# In your LONG/SHORT blocks — after calculating profit_pct:
record_trade(ticker, direction, tf, profit_pct)

def daily_postmortem():
    global last_daily_report
    today = now_pst().date()
    if last_daily_report == today or not daily_trades:
        return

    # Sort by profit % (highest first)
    daily_trades.sort(key=lambda x: x["profit_pct"], reverse=True)

    msg = f"**MARKET CLOSE POST-MORTEM — {today.strftime('%b %d')}**\n\n"
    total_pct = 0
    for trade in daily_trades:
        msg += f"**{trade['tf']} {trade['direction']} {trade['ticker']}** → **+{trade['profit_pct']:.0f}%**\n"
        total_pct += trade['profit_pct']

    msg += f"\n**TOTAL MAX OPTION GAIN TODAY: +{total_pct:.0f}%**"
    send(msg)

    last_daily_report = today
    daily_trades.clear()

# Main loop — call daily post-mortem at close
while True:
    now = now_pst()
    if now.hour == 13 and now.minute == 0 and now.weekday() < 5:  # 4 PM ET = 1 PM PST
        daily_postmortem()
    if now.hour == 6 and now.minute == 20 and now.weekday() < 5:
        premarket_top5()
    if now.hour == 0 and now.minute < 5:
        premarket_done = False
        sent_alerts.clear()
    check_live()
    time.sleep(300)
