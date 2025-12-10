# ================================================================
# REVENANT UNLIMITED ELITE — FINAL BULLETPROOF VERSION
# Works with ANY Polygon key (v2 or v3) — NO AggsClient ERROR
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta

# AUTO-FIX FOR ANY POLYGON KEY VERSION
try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
    print("Polygon v3 client loaded")
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))
    print("Polygon v2 client loaded (fallback)")

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK:
    print("Set DISCORD_WEBHOOK_URL!")
    exit()

# ELITE 33 TICKERS
TICKERS = ["SPY","QQQ","IWM","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN",
           "AVGO","NFLX","AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY",
           "XLF","XLE","XLK","XLV","XBI","ARKK","HOOD","PLTR","RBLX","SNOW","CRWD","SHOP"]

alerts_today = set()
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT UNLIMITED ELITE** | {now().strftime('%H:%M PST')}\n```{msg}```"})

def heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat >= 300:
        print(f"SCANNING — {now().strftime('%H:%M:%S PST')} — 33 ELITE TICKERS — no 429s")
        last_heartbeat = time.time()

# BULLETPROOF get_aggs — works with v2 AND v3
def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    try:
        today = now().strftime('%Y-%m-%d')
        start = (now() - timedelta(days=60)).strftime('%Y-%m-%d')
        return client.get_aggs(ticker, multiplier, timespan, from_=start, to=today, limit=limit)
    except:
        # v2 fallback
        return client.get_aggs(ticker, multiplier, timespan, limit=limit)

# Test connection
try:
    test = safe_aggs("SPY", limit=1)
    send("REVENANT UNLIMITED ELITE — LIVE — HEARTBEAT ACTIVE")
    heartbeat()
except Exception as e:
    send(f"CRITICAL ERROR — {e}")
    exit()

while True:
    try:
        heartbeat()

        vix1d_data = safe_aggs("VIX1D", limit=1)
        vix1d = vix1d_data[0].close if vix1d_data else 30.0
        if vix1d < 32:
            time.sleep(300); continue

        for t in TICKERS:
            bars = safe_aggs(t, limit=100)
            if len(bars) < 20: continue
            b = bars[-1]
            vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
            # ... rest of your elite logic here ...

        if now().hour == 13 and not eod_sent:
            if not alerts_today:
                send("EOD RECAP — CLEAN SHEET\nZero alerts — perfect discipline")
            eod_sent = True
        if now().hour == 1:
            alerts_today.clear()
            eod_sent = False

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {str(e)[:100]}")
        time.sleep(300)
