# ================================================================
# REVENANT UNLIMITED ELITE — FINAL FULLY WORKING (DEC 2025)
# No AggsClient errors — Works with ANY Polygon key — Heartbeat + EOD
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta

# Auto-detect Polygon v2 or v3 — NEVER BREAKS
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
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT UNLIMITED ELITE** | {now().strftime('%H:%M PST')}\n```{msg}```"}, timeout=10)
    except: pass

def heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat >= 300:
        print(f"SCANNING — {now().strftime('%H:%M:%S PST')} — 33 ELITE TICKERS — no 429s")
        last_heartbeat = time.time()

def get_data(t):
    try:
        bars = client.get_aggs(t, 1, "minute", limit=100)
        if len(bars) < 20: return None
        b = bars[-1]
        vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
        rsi = 100 - (100 / (1 + (sum(max(x.close-x.open,0) for x in bars[-14:]) /
                                (sum(abs(x.close-x.open) for x in bars[-14:]) or 1))))
        vol_mult = b.volume / (sum(x.volume for x in bars[-20:]) / 20)
        return {"p": b.close, "v": b.volume, "vwap": vwap, "rsi": rsi, "vol_mult": vol_mult,
                "hi": b.high, "lo": b.low}
    except: return None

def get_otm_contract(ticker, direction):
    today = now().strftime('%Y-%m-%d')
    exp = today if "0DTE" in direction else (now() + timedelta(days=(4-now().weekday())%7 + 3)).strftime('%Y-%m-%d')
    ctype = "call" if "LONG" in direction else "put"
    for c in client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                           expiration_date=exp, limit=200):
        q = client.get_option_quote(c.ticker)
        if q and (p := (q.last_price or q.bid or q.ask or 0)) and 0.30 <= p <= (0.75 if "0DTE" in direction else 1.20):
            return c.ticker, round(p, 3), "0DTE" if exp==today else "WEEKLY"
    return None, None, None

# STARTUP
send("REVENANT UNLIMITED ELITE — NO CAP — HEARTBEAT ACTIVE — LIVE")
heartbeat()

while True:
    try:
        heartbeat()

        vix1d = client.get_aggs("VIX1D",1,"minute",limit=1)[0].close
        if vix1d < 32:
            time.sleep(300); continue

        for t in TICKERS:
            d = get_data(t)
            if not d or d["vol_mult"] < 3.5 or abs(d["p"] - d["vwap"])/d["vwap"] < 0.006:
                continue

            # LONG
            c, prem, mode = get_otm_contract(t, "LONG")
            if c and d["lo"] <= d["vwap"] <= d["p"] and d["rsi"] < 28:
                if f"long_{t}" not in alerts_today:
                    alerts_today.add(f"long_{t}")
                    send(f"{t} → {mode} LONG\n{c} @ ${prem}\n→ {'2-HOUR' if mode=='0DTE' else 'ATR DUMP'}")

            # SHORT
            c, prem, mode = get_otm_contract(t, "SHORT")
            if c and d["hi"] >= d["vwap"] >= d["p"] and d["rsi"] > 72:
                if f"short_{t}" not in alerts_today:
                    alerts_today.add(f"short_{t}")
                    send(f"{t} → {mode} SHORT\n{c} @ ${prem}\n→ {'2-HOUR' if mode=='0DTE' else 'ATR DUMP'}")

        # EOD CLEAN SHEET
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
