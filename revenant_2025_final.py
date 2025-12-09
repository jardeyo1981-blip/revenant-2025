# ================================================================
# REVENANT 9-STRAT NUCLEAR — FINAL FOREVER — ELITE 33 + 5-MIN HEARTBEAT
# REAL OPTIONS % GAIN IN EOD + "SCANNING" LOG EVERY 5 MIN
# ================================================================

import os, time, requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

# ——————— KEYS ———————
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    print("Set MASSIVE_API_KEY and DISCORD_WEBHOOK_URL!")
    exit()

client = RESTClient(api_key=MASSIVE_KEY)

# ——————— ELITE 33 TICKERS ———————
TICKERS = ["SPY","QQQ","IWM","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN",
           "AVGO","NFLX","AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY",
           "XLF","XLE","XLK","XLV","XBI","ARKK","HOOD","PLTR","RBLX","SNOW","CRWD","SHOP"]

MAX_PREMIUM = 0.70
alerts_today = {}   # {key: {"ticker":t, "direction":dir, "contract":c, "entry_prem":p}}
eod_sent_today = False
last_heartbeat = 0

pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT 9-STRAT NUCLEAR** | {now().strftime('%H:%M PST')}\n```{msg}```"}, timeout=10)

# ——————— DATA ———————
def get_price_data(t):
    try:
        bars = client.get_aggs(t, 1, "minute", limit=100)
        if len(bars) < 20: return None
        b = bars[-1]
        vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:])
        ema = b.close
        for x in reversed(bars[:-1]): ema = x.close * 0.075 + ema * 0.925
        return {"price": b.close, "high": b.high, "low": b.low, "open": b.open, "volume": b.volume, "vwap": vwap, "ema": ema}
    except: return None

def get_vix1d():
    try: return client.get_aggs("VIX1D",1,"minute",limit=1)[0].close
    except: return 30.0

def get_cheap_contract(ticker, direction):
    try:
        today = now().strftime('%Y-%m-%d')
        for c in client.list_options_contracts(underlying_ticker=ticker,
            contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=today, limit=150):
            q = client.get_option_quote(c.ticker)
            if q and (p := (q.last_price or q.bid or q.ask or 0)) and 0.01 <= p <= MAX_PREMIUM:
                return c.ticker, c.strike_price, round(p, 3)
    except: pass
    return None, None, None

def track_alert(key, ticker, direction, contract, prem):
    if key not in alerts_today:
        alerts_today[key] = {"ticker": ticker, "direction": direction, "contract": contract, "entry_prem": prem}
        send(f"{ticker} → {direction}\nContract: {contract}\nEntry @ ${prem}\n→ EXECUTE NOW")

# ——————— STARTUP ———————
send("REVENANT 9-STRAT NUCLEAR — ELITE 33 + 5-MIN SCANNING LOG — LIVE")
print(f"SCANNING — {now().strftime('%H:%M:%S PST')} — 33 ELITE TICKERS — no 429s")

# ——————— MAIN LOOP ———————
while True:
    try:
        current_time = time.time()
        hour = now().hour

        # ——— YOUR ORIGINAL 5-MINUTE HEARTBEAT ———
        if current_time - last_heartbeat >= 300:
            print(f"SCANNING — {now().strftime('%H:%M:%S PST')} — 33 ELITE TICKERS — no 429s")
            last_heartbeat = current_time

        vix1d = get_vix1d()

        for t in TICKERS:
            data = get_price_data(t)
            if not data: continue
            p, hi, lo, vwap, ema, vol = data["price"], data["high"], data["low"], data["vwap"], data["ema"], data["volume"]

            call_c, call_s, call_p = get_cheap_contract(t, "LONG")
            put_c, put_s, put_p = get_cheap_contract(t, "SHORT")

            # === ALL 9 STRATEGIES (with tracking) ===
            if t in ["SPY","QQQ"] and 9 <= hour <= 10 and vix1d > 45:
                peak = max(b.high for b in client.get_aggs("VIX1D",1,"minute",limit=50))
                if vix1d < peak*0.85 and p > vwap and call_c:
                    track_alert(f"vix1d_{t}", t, "VIX1D FADE LONG", call_c, call_p)

            if 11 <= hour <= 14 and p > vwap and call_c:
                track_alert(f"ivcrush_{t}", t, "IV CRUSH LONG", call_c, call_p)

            if t in ["NVDA","TSLA","SMCI","MSTR","COIN","AMD"] and vix1d > 35 and vol > 5_000_000 and put_c:
                if p < data["open"] * 0.992:
                    track_alert(f"nuke_{t}", t, "GAMMA NUKE SHORT", put_c, put_p)

            if lo <= ema <= p and call_c: track_alert(f"ema_long_{t}", t, "EMA RETEST LONG", call_c, call_p)
            if hi >= ema >= p and put_c: track_alert(f"ema_short_{t}", t, "EMA RETEST SHORT", put_c, put_p)
            if vwap and lo <= vwap <= p and call_c: track_alert(f"vwap_long_{t}", t, "VWAP RECLAIM LONG", call_c, call_p)
            if vwap and hi >= vwap >= p and put_c: track_alert(f"vwap_short_{t}", t, "VWAP REJECT SHORT", put_c, put_p)
            if vol > 6_000_000 and p < vwap and put_c: track_alert(f"po3_{t}", t, "PO3 NUCLEAR SHORT", put_c, put_p)
            if lo < client.get_aggs(t,1,"minute",limit=20)[-10].low and p > vwap and call_c:
                track_alert(f"snap_{t}", t, "SNAP-BACK LONG", call_c, call_p)

        # ——————— EOD RECAP WITH REAL OPTIONS % GAIN ———————
        if 12 <= hour <= 13 and not eod_sent_today:
            if alerts_today:
                recap = "EOD RECAP — REAL 0DTE OPTIONS P&L\n\n"
                wins = total = 0
                for info in alerts_today.values():
                    try:
                        q = client.get_option_quote(info["contract"])
                        curr = q.last_price or q.bid or q.ask or info["entry_prem"]
                        gain = (curr - info["entry_prem"]) / info["entry_prem"] * 100
                        total += gain
                        wins += 1 if gain > 0 else 0
                        recap += f"{'WIN' if gain>0 else 'LOSS'} {info['ticker']} {info['direction']}\n   {info['contract']} | ${info['entry_prem']} → ${curr:.3f} | {gain:+.1f}%\n"
                    except: recap += f"{info['ticker']} → no quote\n"
                recap += f"\nWINS: {wins}/{len(alerts_today)} | AVG GAIN: {total/len(alerts_today):+.1f}%"
                send(recap)
            else:
                send("EOD RECAP — CLEAN SHEET\nZero alerts — perfect discipline")
            eod_sent_today = True

        if hour == 1:
            alerts_today.clear()
            eod_sent_today = False

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {str(e)[:100]}")
        time.sleep(300)
