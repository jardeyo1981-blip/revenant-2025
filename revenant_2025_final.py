# ================================================================
# REVENANT — FULL RIPSTER TENETS FINAL (DEC 11 2025)
# 100% Fixed — No More Index Errors — Live Forever
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta
from statistics import median

# POLYGON CLIENT
try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK:
    print("Set DISCORD_WEBHOOK_URL!")
    exit()

TICKERS = ["SPY","QQQ","IWM","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN",
           "AVGO","NFLX","AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY",
           "XLF","XLE","XLK","XLV","XBI","ARKK","HOOD","PLTR","RBLX","SNOW","CRWD","SHOP"]

alerts_today = set()
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT RIPSTER FINAL** | {now().strftime('%H:%M PST')}\n```{msg}```"})

# DYNAMIC VIX THRESHOLD (75th percentile)
def get_dynamic_vix_threshold():
    try:
        raw = client.get_aggs("^VIX", 1, "day", limit=40)
        closes = [b.close for b in raw[-22:]]
        return max(sorted(closes)[int(len(closes)*0.75)], 14.0)
    except:
        return 16.0

# BULLETPROOF AGGS + RATE LIMIT PROTECTION
def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    for _ in range(3):
        try:
            resp = client.get_aggs(ticker, multiplier, timespan, limit=limit)
            if resp and len(resp) > 0:
                return resp
        except:
            pass
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}"
            params = {"adjusted":"true","limit":limit,"apiKey":os.getenv("MASSIVE_API_KEY")}
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if "results" in data and len(data["results"]) > 0:
                    return [type('obj', (), x) for x in data["results"]]
        except:
            pass
        time.sleep(1)
    return []

# 15-MIN MTF VWAP SLOPE
def mtf_vwap_slope(ticker):
    try:
        bars15 = safe_aggs(ticker, 15, "minute", limit=20)
        if len(bars15) < 10: return 0
        vwap_old = sum((b.vwap or b.close)*b.volume for b in bars15[-10:-5]) / sum(b.volume for b in bars15[-10:-5])
        vwap_new = sum((b.vwap or b.close)*b.volume for b in bars15[-5:]) / sum(b.volume for b in bars15[-5:])
        return 1 if vwap_new > vwap_old else -1 if vwap_new < vwap_old else 0
    except:
        return 0

# TARGET PRICE — 1.45× ATR
def get_target_price(ticker, direction, current_price):
    try:
        daily = safe_aggs(ticker, 1, "day", limit=20)
        atr = sum(b.high - b.low for b in daily[-14:]) / 14
    except:
        atr = current_price * 0.015
    move = atr * 1.45
    return round(current_price + (move if "LONG" in direction else -move), 2)

# NEAR-OTM 0DTE CONTRACT PICKER
def get_contract(ticker, direction):
    today = now().strftime('%Y-%m-%d')
    ctype = "call" if "LONG" in direction else "put"
    try:
        contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                                  expiration_date=today, limit=200)
    except:
        return None, None, None
    spot = safe_aggs(ticker, limit=1)
    if not spot: return None, None, None
    spot = spot[-1].close
    candidates = []
    for c in contracts:
        try:
            q = client.get_option_quote(c.ticker)
            if not q or q.ask is None or q.ask > 18 or q.bid < 0.10: continue
            strike = float(c.ticker.split(ctype.upper())[-1])
            dist = abs(strike - spot) / spot
            if dist <= 0.048:
                spread_pct = (q.ask - q.bid) / q.ask if q.ask > 0 else 1
                if spread_pct <= 0.35 and getattr(q, 'open_interest', 0) > 300:
                    candidates.append((q.ask, getattr(q, 'open_interest', 0), dist, c.ticker))
        except: continue
    if candidates:
        candidates.sort(key=lambda x: (-x[1], x[0], x[2]))
        best = candidates[0]
        return best[3], round(best[0], 2), "0DTE"
    return None, None, None

# LAUNCH
send("REVENANT RIPSTER FINAL — FULL TENETS — LIVE FOREVER")
print("Today’s dynamic VIX threshold:", get_dynamic_vix_threshold())

while True:
    try:
        if time.time() - last_heartbeat >= 300:
            print(f"SCANNING {now().strftime('%H:%M PST')} | VIX thresh {get_dynamic_vix_threshold():.1f}")
            last_heartbeat = time.time()

        # Skip first 15 minutes
        if now().hour == 6 and now().minute < 45:
            time.sleep(60)
            continue

        # SAFE VIX1D READ — NO MORE INDEX ERROR
        vix_bars = safe_aggs("VIX1D", limit=2)
        if len(vix_bars) == 0:
            time.sleep(300)
            continue
        vix1d = vix_bars[-1].close

        if vix1d < get_dynamic_vix_threshold():
            time.sleep(300)
            continue

        for t in TICKERS:
            bars = safe_aggs(t, limit=100)
            if len(bars) < 30: continue
            b = bars[-1]
            current_price = b.close

            # VWAP + Volume
            vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
            vol_mult = b.volume / (sum(x.volume for x in bars[-20:]) / 20)

            # RSI + 3-bar curl
            gains = sum(max(x.close-x.open,0) for x in bars[-14:])
            losses = sum(abs(x.close-x.open) for x in bars[-14:]) or 1
            rsi = 100 - (100 / (1 + gains/losses))
            rsi3 = []
            for i in range(1, 4):
                g = sum(max(x.close-x.open,0) for x in bars[-14-i:-i])
                l = sum(abs(x.close-x.open) for x in bars[-14-i:-i]) or 1
                rsi3.append(100 - (100 / (1 + g/l)))
            rsi_curl_up = rsi3[0] > rsi3[1] > rsi3[2]
            rsi_curl_down = rsi3[0] < rsi3[1] < rsi3[2]

            ema5 = sum(x.close for x in bars[-5:]) / 5
            mtf = mtf_vwap_slope(t)

            if vol_mult < 2.65 or abs(current_price - vwap)/vwap < 0.0042:
                continue

            # LONG — FULL RIPSTER STACK
            if (current_price > vwap and current_price > ema5 and rsi < 34 and 
                rsi_curl_up and mtf >= 0 and b.low <= vwap <= current_price):
                c, prem, _ = get_contract(t, "LONG")
                if c and f"long_{t}" not in alerts_today:
                    alerts_today.add(f"long_{t}")
                    target = get_target_price(t, "LONG", current_price)
                    send(f"{t} 0DTE LONG → ${prem}\nTarget ${target}\n{c}")

            # SHORT — FULL RIPSTER STACK
            if (current_price < vwap and current_price < ema5 and rsi > 66 and 
                rsi_curl_down and mtf <= 0 and b.high >= vwap >= current_price):
                c, prem, _ = get_contract(t, "SHORT")
                if c and f"short_{t}" not in alerts_today:
                    alerts_today.add(f"short_{t}")
                    target = get_target_price(t, "SHORT", current_price)
                    send(f"{t} 0DTE SHORT → ${prem}\nTarget ${target}\n{c}")

        if now().hour >= 13 and not eod_sent:
            send(f"EOD — {len(alerts_today)} RIPSTER-GRADE alerts today")
            eod_sent = True
        if now().hour == 1:
            alerts_today.clear()
            eod_sent = False

        time.sleep(300)
    except Exception as e:
        send(f"ERROR alive: {str(e)[:100]}")
        time.sleep(300)
