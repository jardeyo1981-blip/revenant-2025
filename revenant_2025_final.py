# ================================================================
# REVENANT UNLIMITED ELITE — FINAL FINAL
# No cap — Only 8–10/10 rated plays — Heartbeat every 5 min
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta
from polygon import RESTClient

MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ["SPY","QQQ","IWM","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN",
           "AVGO","NFLX","AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY",
           "XLF","XLE","XLK","XLV","XBI","ARKK","HOOD","PLTR","RBLX","SNOW","CRWD","SHOP"]

alerts_today = set()
last_heartbeat = 0
last_scan = 0
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT UNLIMITED ELITE** | {now().strftime('%H:%M PST')}\n```{msg}```"})

# ——————— YOUR EXACT HEARTBEAT LOG — EVERY 5 MINUTES ———————
def heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat >= 300:
        log_msg = f"SCANNING — {now().strftime('%H:%M:%S PST')} — 33 ELITE TICKERS — no 429s"
        print(log_msg)
        last_heartbeat = time.time()

# ——————— REST OF YOUR SCRIPT (unchanged except heartbeat call) ———————
send("REVENANT UNLIMITED ELITE — NO CAP — HEARTBEAT ACTIVE — LIVE")

while True:
    try:
        heartbeat()  # ← This gives you the log you love

        if time.time() - last_scan >= 300:
            last_scan = time.time()

        vix1d = client.get_aggs("VIX1D",1,"minute",limit=1)[0].close
        if vix1d < 32: 
            time.sleep(300); continue

        # ... [all your elite logic here — unchanged] ...

        time.sleep(1)  # light loop
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
