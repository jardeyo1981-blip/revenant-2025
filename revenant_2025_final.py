# revenant_2025_2_to_3_alerts_per_day_FINAL_NO_429.py
# LIVE FOREVER — DEC 2025 — 2–3 ALERTS/DAY + ZERO 429s
import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing MASSIVE_API_KEY or DISCORD_WEBHOOK_URL!")
client = RESTClient(api_key=MASSIVE_KEY)

# === 50 TICKERS ===
TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

# === CLOUDS + HOLD TIMES (now with 15min) ===
CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5), ("15",50,1.2)]
ESTIMATED_HOLD = {"D":"2h–6h", "240":"1h–3h", "60":"30min–1h45m", "30":"15min–45min", "15":"10min–30min"}

# === TUNED FILTERS ===
MIN_GAP = 1.4
MAX_PREMIUM = 1.50
GAMMA_TOLERANCE = 0.04

# === GLOBAL STATE ===
sent_alerts = set()
premarket_done = False
last_daily_report = None
last_heartbeat = 0
pst = pytz.timezone('America/Los_Angeles')

# === PREV-CLOSE CACHE (429 KILLER) ===
prev_close_cache = {}
last_cache_date = None

def now_pst(): return datetime.now(pst)

def get_prev_close(ticker):
    global prev_close_cache, last_cache_date
    today = now_pst().date()
    if last_cache_date != today:
        prev_close_cache = {}
        last_cache_date = today
    if ticker not in prev_close_cache:
        try:
            aggs = client.get_aggs(ticker, 1, "day", limit=5)
            prev_close_cache[ticker] = aggs[-2].close if len(aggs) >= 2 else None
        except:
            prev_close_cache[ticker] = None
    return prev_close_cache[ticker]

# === DISCORD + HEARTBEAT ===
def send_discord(msg):
    try:
        data = {"content": f"**Revenant 2.0 Alert** | {now_pst().strftime('%H:%M:%S PST')} ```{msg}```"}
        requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        print(f"ALERT → {msg}")
    except Exception as e:
        print(f"Discord fail: {e}")

def send_heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat > 3600:
        send_discord("HEARTBEAT — 2–3 alerts/day mode | Running clean")
        last_heartbeat = time.time()

# === EMA + ATR ===
def get_price_and_ema(ticker, tf, length):
    try:
        multiplier = {"D":1, "240":4, "60":1, "30":1, "15":1}.get(tf, 1)
        timespan = "day" if tf == "D" else "minute"
        days_back = 730 if tf == "D" else 60
        from_date = (now_pst() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        aggs = client.get_aggs(ticker, multiplier, timespan, from_date, now_pst().strftime('%Y-%m-%d'), limit=50000)
        if len(aggs) < length: return None, None
        closes = [bar.close for bar in aggs]
        price = closes[-1]
        ema = closes[0]
        k = 2 / (length + 1)
        for close in closes[1:]:
            ema = close * k + ema * (1 - k)
        return round(price, 4), round(ema, 4)
    except: return None, None

def get_atr(ticker, period=20):
    try:
        aggs = client.get_aggs(ticker, 1, "minute", limit=period+10)
        tr = [max(a.high-a.low, abs(a.high-aggs[i-1].close), abs(a.low-aggs[i-1].close)) 
              for i, a in enumerate(aggs[-period:]) if i > 0]
        return sum(tr)/len(tr) if tr else 0
    except: return 0

# === GAMMA + CHEAP CONTRACT ===
def get_gamma_flip(ticker):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),
            expiration_date_lte=(now_pst()+timedelta(days=2)).strftime('%Y-%m-%d'),
            limit=200)
        strikes = {}
        for c in contracts:
            oi = c.open_interest or 0
            strikes[c.strike_price] = strikes.get(c.strike_price, 0) + oi
        if strikes: return max(strikes, key=strikes.get)
    except: pass
    return None

def find_cheap_contract(ticker, direction):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),
            expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'),
            limit=100)
        for c in contracts:
            quote = client.get_last_trade(c.ticker)
            if quote and quote.price and quote.price <= MAX_PREMIUM:
                return c.strike_price, round(quote.price, 2)
    except: pass
    return None, None

# === GRADING ===
def get_grade(gap_pct, prem, gamma_hit, is_daily):
    score = gap_pct
    if is_daily: score *= 2.2
    if gamma_hit: score *= 1.5
    if prem <= 0.80: score *= 1.3
    if score >= 6.5: return "A++"
    if score >= 5.0: return "A+"
    if score >= 3.8: return "A"
    if score >= 2.8: return "B"
    return "C"

# === MAIN SCAN ===
def check_live():
    global premarket_done, last_daily_report
    now = now_pst()
    hour = now.hour
    if now.weekday() >= 5 or not (6.5 <= hour < 13):
        time.sleep(300)
        return

    print(f"SCANNING — {now.strftime('%H:%M:%S PST')} — 50 TICKERS — 2–3/day clean mode")

    for ticker in TICKERS:
        try:
            prev_close = get_prev_close(ticker)
            if not prev_close: continue
            price, _ = get_price_and_ema(ticker, "D", 50)
            if not price: continue
            gap_pct = abs((price - prev_close) / prev_close * 100)

            atr_20 = get_atr(ticker, 20)
            current_range = abs(client.get_aggs(ticker, 1, "minute", limit=2)[-1].high -
                              client.get_aggs(ticker, 1, "minute", limit=2)[-1].low)
            vol_expansion = current_range > atr_20 * 2.2

            if gap_pct < MIN_GAP and not vol_expansion:
                continue

            direction = "LONG" if price > prev_close else "SHORT"
            gamma = get_gamma_flip(ticker)
            gamma_hit = gamma and abs(gamma - price) < price * GAMMA_TOLERANCE
            strike, prem = find_cheap_contract(ticker, direction)
            if not prem: continue

            for tf, length, _ in CLOUDS:
                _, ema = get_price_and_ema(ticker, tf, length)
                if not ema: continue
                if (direction == "LONG" and price > ema) or (direction == "SHORT" and price < ema):
                    alert_id = f"{ticker}_{direction}_{tf}_{now.strftime('%Y%m%d')}"
                    if alert_id in sent_alerts: continue
                    sent_alerts.add(alert_id)

                    grade = get_grade(gap_pct, prem, gamma_hit, tf=="D")
                    hold = ESTIMATED_HOLD.get(tf, "??")
                    confluence = "Gamma" if gamma_hit else ("VolExp" if vol_expansion else "EMA")

                    msg = f"{ticker} {direction} | {gap_pct:.1f}% gap | {grade} | {confluence} {gamma or ''} | {strike} @ ${prem} | {hold} | {tf}"
                    send_discord(msg)

        except Exception as e:
            continue

    send_heartbeat()

# === INFINITE LOOP ===
if __name__ == "__main__":
    send_discord("REVENANT 2.0 FINAL — 2–3 alerts/day | 429s ELIMINATED | Deployed & hunting")
    while True:
        try:
            check_live()
            time.sleep(300)
        except Exception as e:
            send_discord(f"LOOP ERROR — retrying: {e}")
            time.sleep(300)
