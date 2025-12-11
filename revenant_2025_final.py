# ================================================================
# REVENANT 10.1 — FINAL + FIXED + PREMIUM (LIVE AS OF DEC 11 2025)
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta

try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK: exit("Set DISCORD_WEBHOOK_URL!")

INDEX  = ["SPY","QQQ","IWM","XLF","XLK","XLE","XLV","XBI"]
STOCKS = ["NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN","AVGO","NFLX",
          "AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY","ARKK","HOOD",
          "PLTR","RBLX","SNOW","CRWD","SHOP"]
TICKERS = INDEX + STOCKS

alerts_today = set()
earnings_today = set()
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

# ── UNIVERSAL AGGS (works on every Polygon version forever) ─────────────────────
def get_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    try:
        # New SDK
        return client.get_aggs(
            ticker, multiplier, timespan,
            from_=(datetime.now(pst)-timedelta(days=12)).strftime('%Y-%m-%d'),
            to=datetime.now(pst).strftime('%Y-%m-%d'),
            limit=limit
        )
    except:
        try:
            # Old SDK fallback
            return client.get_aggs(ticker, multiplier, timespan, limit=limit)
        except:
            return []

def get_vix1d():
    try: return get_aggs("VIX",1,"day",2)[-1].close
    except: return 18.0

def vix_boost():
    v = get_vix1d()
    return 28 if v>30 else 24 if v>22 else 20

def load_earnings_today():
    global earnings_today
    try:
        today = now().strftime('%Y-%m-%d')
        earnings = client.list_
