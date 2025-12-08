# revenant_2025_FINAL_WITH_PROFIT.py
# PERFECT BTC-BOT STYLE + EXPECTED PROFIT + GREEN/RED + TEST MODE
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

TICKERS = ['SPY','QQQ','TSLA','NVDA','AAPL','AMD','MSFT','AMZN','META','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]
ESTIMATED_HOLD = {"D":"2h – 6h", "240":"1h – 3h", "60":"30min – 1h45m", "30":"15min – 45min"}

sent_alerts = set()
last_test = 0
premarket_sent = False
TEST_MODE = True                    # ← SET TO False FOR LIVE
TEST_INTERVAL = 120                 # 2 minutes

pst = pytz.timezone('America/Los_Angeles')

def now_pst():
    return datetime.now(pst)

def send(text):
    payload = {"content": text}
    try:
        requests.post(DISCORD_WEBHOOK, json=payload)
        print(f"{now_pst().strftime('%H:%M PST')} → Alert sent")
    except: print("Discord failed")

# TEST MODE — 2-minute fake alerts + fake pre-market
def test_mode():
    global last_test, premarket_sent
    if time.time() - last_test < TEST_INTERVAL:
        return
    last_test = time.time()

    if not premarket_sent:
        send("**6:20 AM PST — PRE-MARKET TOP 5**\n\n"
             "1. NVDA → DAILY `188.20` (**+4.2%**) 🌙\n"
             "2. TSLA → 4H `442.10` (**-3.1%**) 🔥\n"
             "3. SMCI → 1H `445.60` (**+3.8%**) 🚀\n"
             "4. SPY → DAILY `698.50` (**+2.1%**) 💵\n"
             "5. QQQ → 1H `610.00` (**-2.5%**) ⭐")
        premarket_sent = True

    examples = [
        ("DAILY LONG NVDA 🌙", "LONG", "`182.41` → `188.20` (+3.17%)", "Gamma Flip $185.00", "185 @ $0.52", "$0.52 → $2.18 (+319%)", "2h – 6h"),
        ("60 SHORT TSLA 🔥", "SHORT", "`454.61` → `442.10` (-2.75%)", "No confluence", "450 @ $0.68", "$0.68 → $2.30 (+238%)", "30min – 1h45m"),
        ("30 LONG AMD 🚀", "LONG", "`172.40` → `175.80` (+1.97%)", "Confluence!", "175 @ $0.59", "$0.59 → $1.81 (+207%)", "15min – 45min"),
        ("4H LONG SPY 💵", "LONG", "`685.20` → `698.50` (+1.94%)", "Gamma Flip $690.00", "690 @ $0.78", "$0.78 → $2.34 (+200%)", "1h – 3h"),
        ("DAILY SHORT QQQ ⭐", "SHORT", "`625.50` → `610.00` (-2.48%)", "Confluence!", "620 @ $0.81", "$0.81 → $2.67 (+230%)", "2h – 6h")
    ]
    title, direction, entry_target, gamma, opt, profit, hold = random.choice(examples)
    color = "🟩" if direction == "LONG" else "🟥"
    send(f"{color} **TEST MODE — {title}**\n\n"
         f"**Entry → Target**\n{entry_target}\n\n"
         f"**Gamma Flip**\n{gamma}\n\n"
         f"**Option**\n{opt}\n\n"
         f"**Profit if target hit**\n{profit}\n\n"
         f"**Hold**\n{hold}")

# LIVE ALERT — 100% LIKE YOUR BTC BOT + EXPECTED PROFIT
def send_live_alert(tf, direction, ticker, price, target, gap_pct, gamma_text, opt, hold, profit_line):
    tf_name = "DAILY" if tf == "D" else tf
    color = "🟩" if direction == "LONG" else "🟥"
    style = "BULLISH" if direction == "LONG" else "BEARISH"
    
    msg = f"{color} **{style}**\n" \
          f"**{tf_name} {ticker}**\n\n" \
          f"**Entry → Target**\n" \
          f"`{price:.2f}` → `{target:.2f}` ({'+' if direction=='LONG' else '-'}{gap_pct:.2f}%)\n\n" \
          f"**Gamma Flip**\n{gamma_text}\n\n" \
          f"**Option**\n{opt}\n\n" \
          f"**Profit if target hit**\n{profit_line}\n\n" \
          f"**Hold**\n{hold}\n" \
          f"{now_pst().strftime('%H:%M:%S PST')}"
    
    send(msg)

# [All your real functions here — get_ema, get_gamma_flip, find_cheap_contract, premarket_top5, check_live]

# Inside check_live() — replace send() calls with:
# direction = "LONG" if price < ema else "SHORT"
# profit_line = f"${prem:.2f} → ${new_price:.2f} (+{profit_pct:.0f}%)" if prem else "No <$1 contract"
# send_live_alert(tf, direction, ticker, price, ema, gap_pct, gamma_text, opt, ESTIMATED_HOLD[tf], profit_line)

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
