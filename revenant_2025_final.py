# ================================================================
# REVENANT — FULL RIPSTER TENETS EDITION (DEC 11 2025)
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta
from statistics import median

try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK: exit("Set DISCORD_WEBHOOK_URL!")

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

def get_dynamic_vix_threshold():
    try:
        raw = client.get_aggs("^VIX", 1, "day", limit=40)
        closes = [b.close for b in raw[-22:]]
        return max(sorted(closes)[int(len(closes)*0.75)], 14.0)
    except: return 16.0

def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    try: return client.get_aggs(ticker, multiplier, timespan, limit=limit)
    except:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}"
        params = {"adjusted":"true","limit":limit,"apiKey":os.getenv("MASSIVE_API_KEY")}
        try:
            r = requests.get(url, params=params, timeout=20)
            data = r.json()
            if "results" in data: return [type('obj', (), x) for x in data["results"]]
        except: pass
        return []

def mtf_vwap_slope(ticker):
    try:
        bars15 = safe_aggs(ticker, 15, "minute", limit=20)
        if len(bars15) < 10: return 0
        vwap_old = sum((b.vwap or b.close)*b.volume for b in bars15[-10:-5]) / sum(b.volume for b in bars15[-10:-5])
        vwap_new = sum((b.vwap or b.close)*b.volume for b in bars15[-5:]) / sum(b.volume for b in bars15[-5:])
        return 1 if vwap_new > vwap_old else -1 if vwap_new < vwap_old else 0
    except: return 0

def get_target_price(ticker, direction, current_price):
    try:
        daily = safe_aggs(ticker, 1, "day", limit=20)
        atr = sum(b.high - b.low for b in daily[-14:]) / 14
    except: atr = current_price * 0.015
    return round(current_price + (atr * 1.45 if "LONG" in direction else -atr * 1.45), 2)

def get_contract(ticker, direction):
    today = now().strftime('%Y-%m-%d')
    ctype = "call" if "LONG" in direction else "put"
    contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                              expiration_date=today, limit=200)
    spot = safe_aggs(ticker, limit=1)[-1].close
    candidates = []
    for c in contracts:
        try:
            q = client.get_option_quote(c.ticker)
            if not q or q.ask is None or q.ask > 18 or q.bid < 0.10: continue
            strike = float(c.ticker.split(ctype.upper())[-1])
            dist = abs(strike - spot) / spot
            if dist <= 0.048:
                spread_pct = (q.ask - q.bid) / q.ask
                if spread_pct <= 0.35 and q.open_interest > 300:
                    candidates.append((q.ask, q.open_interest, dist, c.ticker))
        except: continue
    if candidates:
        candidates.sort(key=lambda x: (-x[1], x[0], x[2]))
        best = candidates[0]
        return best[3], round(best[0], 2), "0DTE"
    return None, None, None

send("REVENANT RIPSTER FINAL — FULL TENETS — LIVE")
print("VIX threshold today:", get_dynamic_vix_threshold())

while True:
    try:
        if time.time() - last_heartbeat >= 300:
            print(f"SCANNING {now().strftime('%H:%M PST')} | VIX thresh {get_dynamic_vix_threshold():.1f}")
            last_heartbeat = time.time()

        if now().hour == 6 and now().minute < 45:  # skip first 15 min
            time.sleep(60); continue

        if safe_aggs("VIX1D", limit=1)[0].close < get_dynamic_vix_threshold():
            time.sleep(300); continue

        for t in TICKERS:
            bars = safe_aggs(t, limit=100)
            if len(bars) < 30: continue
            b = bars[-1]; current_price = b.close
            vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
            vol_mult = b.volume / (sum(x.volume for x in bars[-20:]) / 20)

            gains = sum(max(x.close-x.open,0) for x in bars[-14:])
            losses = sum(abs(x.close-x.open) for x in bars[-14:]) or 1
            rsi = 100 - (100 / (1 + gains/losses))
            rsi3 = [100 - (100 / (1 + sum(max(x.close-x.open,0) for x in bars[-14-i:-i]) /
                                  (sum(abs(x.close-x.open) for x in bars[-14-i:-i]) or 1))) for i in range(1,4)]
            rsi_curl_up = rsi3[0] > rsi3[1] > rsi3[2]
            rsi_curl_down = rsi3[0] < rsi3[1] < rsi3[2]

            ema5 = sum(b.close for b in bars[-5:]) / 5
            mtf = mtf_vwap_slope(t)

            if vol_mult < 2.65 or abs(current_price - vwap)/vwap < 0.0042: continue

            # LONG
            if (current_price > vwap and current_price > ema5 and rsi < 34 and rsi_curl_up and mtf >= 0 and b.low <= vwap <= current_price):
                c, prem, _ = get_contract(t, "LONG")
                if c and f"long_{t}" not in alerts_today:
                    alerts_today.add(f"long_{t}")
                    target = get_target_price(t, "LONG", current_price)
                    send(f"{t} 0DTE LONG → ${prem}\nTarget ${target}\n{c}")

            # SHORT
            if (current_price < vwap and current_price < ema5 and rsi > 66 and rsi_curl_down and mtf <= 0 and b.high >= vwap >= current_price):
                c, prem, _ = get_contract(t, "SHORT")
                if c and f"short_{t}" not in alerts_today:
                    alerts_today.add(f"short_{t}")
                    target = get_target_price(t, "SHORT", current_price)
                    send(f"{t} 0DTE SHORT → ${prem}\nTarget ${target}\n{c}")

        if now().hour >= 13 and not eod_sent:
            send(f"EOD — {len(alerts_today)} RIPSTER alerts today")
            eod_sent = True
        if now().hour == 1:
            alerts_today.clear(); eod_sent = False

        time.sleep(300)
    except Exception as e:
        send(f"ERROR: {str(e)[:100]}")
        time.sleep(300)
