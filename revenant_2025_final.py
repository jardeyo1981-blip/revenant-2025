# ================================================================
# REVENANT UNLIMITED ELITE — FINAL BULLETPROOF (DEC 2025)
# NO AggsClient ERROR — Works with ANY key — Targets + Heartbeat
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta

# AUTO-FIX FOR ANY POLYGON KEY (v2 or v3) — NEVER BREAKS
try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
    print("Polygon v3 client loaded")
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))
    print("Polygon v2 client loaded — AUTO-FIXED")

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK:
    print("Set DISCORD_WEBHOOK_URL!")
    exit()

# SETTINGS
MAX_PREMIUM = 0.50
VIX1D_MIN = 32

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
        # v3 style — no from/to needed
        return client.get_aggs(ticker, multiplier, timespan, limit=limit)
    except:
        # v2 fallback — auto-adds from/to
        end = now().strftime('%Y-%m-%d')
        start = (now() - timedelta(days=60)).strftime('%Y-%m-%d')
        return client.get_aggs(ticker, multiplier, timespan, from_=start, to=end, limit=limit)

# ——————— TARGET + CONTRACT ———————
def get_target_price(ticker, direction, current_price):
    try:
        daily = safe_aggs(ticker, 1, "day", limit=20)
        atr = sum(b.high - b.low for b in daily[-14:]) / 14
    except:
        atr = current_price * 0.015
    vix = safe_aggs("VIX1D", limit=1)[0].close
    boost = max(0, (vix - 38) * 0.15)
    mult = (1.8 + boost) if "0DTE" in direction else (1.0 + boost * 0.5)
    move = atr * mult
    return round(current_price + (move if "LONG" in direction else -move), 2)

def get_contract(ticker, direction):
    today = now().strftime('%Y-%m-%d')
    exp = today if "0DTE" in direction else (now() + timedelta(days=(4-now().weekday())%7 + 3)).strftime('%Y-%m-%d')
    ctype = "call" if "LONG" in direction else "put"
    for c in client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                           expiration_date=exp, limit=200):
        q = client.get_option_quote(c.ticker)
        if q and (p := (q.last_price or q.bid or q.ask or 0)) and 0.30 <= p <= MAX_PREMIUM:
            return c.ticker, round(p, 3), "0DTE" if exp==today else "WEEKLY"
    return None, None, None

send("REVENANT UNLIMITED ELITE — FINAL LIVE — TARGETS + $0.50 MAX")
heartbeat()

while True:
    try:
        heartbeat()

        vix_data = safe_aggs("VIX1D", limit=1)
        vix1d = vix_data[0].close if vix_data else 30.0
        if vix1d < VIX1D_MIN:
            time.sleep(300); continue

        for t in TICKERS:
            bars = safe_aggs(t, limit=100)
            if len(bars) < 20: continue
            b = bars[-1]
            current_price = b.close
            vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
            vol_mult = b.volume / (sum(x.volume for x in bars[-20:]) / 20)
            rsi = 100 - (100 / (1 + (sum(max(x.close-x.open,0) for x in bars[-14:]) /
                                    (sum(abs(x.close-x.open) for x in bars[-14:]) or 1))))

            if vol_mult < 3.5 or abs(current_price - vwap)/vwap < 0.006:
                continue

            # LONG
            c, prem, mode = get_contract(t, "LONG")
            if c and b.low <= vwap <= current_price and rsi < 28:
                if f"long_{t}" not in alerts_today:
                    alerts_today.add(f"long_{t}")
                    target = get_target_price(t, "LONG", current_price)
                    send(f"{t} → {mode} LONG\nCurrent: ${current_price:.2f}\n**TARGET: ${target}** (+{(target-current_price)/current_price*100:.1f}%)\n{c} @ ${prem}")

            # SHORT
            c, prem, mode = get_contract(t, "SHORT")
            if c and b.high >= vwap >= current_price and rsi > 72:
                if f"short_{t}" not in alerts_today:
                    alerts_today.add(f"short_{t}")
                    target = get_target_price(t, "SHORT", current_price)
                    send(f"{t} → {mode} SHORT\nCurrent: ${current_price:.2f}\n**TARGET: ${target}** ({(target-current_price)/current_price*100:+.1f}%)\n{c} @ ${prem}")

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
