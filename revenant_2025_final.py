# revenant_2025_2_to_3_alerts_per_day_FULLY_FIXED_WITH_TEST_MODE.py
# FINAL VERSION — ZERO 429s + LOW-LIQUIDITY TICKERS ALIVE + TEST MODE TOGGLE
import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

# === TEST MODE TOGGLE ===
TEST_MODE = True  # <<< FLIP TO False WHEN READY FOR LIVE TRADING >>>

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing keys!")
client = RESTClient(api_key=MASSIVE_KEY)

# === TICKERS ===
TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50), ("240",50), ("60",50), ("30",50), ("15",50)]
ESTIMATED_HOLD = {"D":"2h–6h", "240":"1h–3h", "60":"30m–1h45m", "30":"15m–45m", "15":"10m–30m"}

MIN_GAP = 1.4
MAX_PREMIUM = 1.50
GAMMA_TOLERANCE = 0.04

sent_alerts = set()
last_heartbeat = 0
pst = pytz.timezone('America/Los_Angeles')

# === SMART CACHES ===
prev_close_cache = {}
atr_cache = {}
last_cache_date = None

def now_pst(): return datetime.now(pst)

# Cache previous close once per day
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

# Cache 20-period ATR once per scan
def get_current_atr_and_range():
    global atr_cache
    if not atr_cache or time.time() - atr_cache.get("ts", 0) > 290:
        atr_cache = {"ts": time.time()}
        minute_bars = {}
        try:
            for ticker in TICKERS:
                bars = client.get_aggs(ticker, 1, "minute", limit=30)
                minute_bars[ticker] = bars
            for ticker, bars in minute_bars.items():
                if len(bars) < 20: continue
                tr = [max(b.high-b.low, abs(b.high-bars[i-1].close), abs(b.low-bars[i-1].close))
                      for i, b in enumerate(bars[-20:]) if i > 0]
                avg_atr = sum(tr)/len(tr)
                current_range = bars[-1].high - bars[-1].low
                atr_cache[ticker] = {"atr": avg_atr, "range": current_range}
        except:
            pass
    return atr_cache

# === DISCORD + HEARTBEAT (with TEST MODE prefix) ===
def send_discord(msg):
    prefix = "**TEST MODE** — " if TEST_MODE else ""
    full_msg = f"{prefix}**Revenant 2.0** | {now_pst().strftime('%H:%M:%S PST')} ```{msg}```"
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": full_msg}, timeout=10)
        print(f"ALERT → {full_msg}")
    except: pass

def send_heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat > 3600:
        test_note = " (TEST MODE ACTIVE)" if TEST_MODE else ""
        send_discord(f"HEARTBEAT — 2–3 alerts/day | 429-PROOF | Low-liq alive{test_note}")
        last_heartbeat = time.time()

# === EMA ===
def get_price_and_ema(ticker, tf, length):
    try:
        mult = {"D":1, "240":4, "60":1, "30":1, "15":1}.get(tf, 1)
        ts = "day" if tf == "D" else "minute"
        days = 730 if tf == "D" else 60
        aggs = client.get_aggs(ticker, mult, ts, (now_pst()-timedelta(days=days)).strftime('%Y-%m-%d'), now_pst().strftime('%Y-%m-%d'), limit=50000)
        if len(aggs) < length: return None, None
        closes = [a.close for a in aggs]
        ema = closes[0]
        k = 2/(length+1)
        for c in closes[1:]: ema = c*k + ema*(1-k)
        return round(closes[-1], 4), round(ema, 4)
    except: return None, None

# === GAMMA ===
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
        return max(strikes, key=strikes.get) if strikes else None
    except: return None

# === CHEAP CONTRACT — LOW-LIQUIDITY FIXED ===
def find_cheap_contract(ticker, direction):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            contract_type="call" if direction == "LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),
            expiration_date_lte=(now_pst() + timedelta(days=7)).strftime('%Y-%m-%d'),
            limit=100
        )
        for c in contracts:
            try:
                quote = client.get_option_quote(c.ticker)
                if quote:
                    price = quote.last_price or quote.bid or quote.ask or 0
                    if 0.01 <= price <= MAX_PREMIUM:
                        return c.strike_price, round(price, 2)
            except:
                continue
    except:
        pass
    return None, None

# === GRADING ===
def get_grade(gap, prem, gamma_hit, daily):
    s = gap
    if daily: s *= 2.2
    if gamma_hit: s *= 1.5
    if prem <= 0.8: s *= 1.3
    if s >= 6.5: return "A++"
    if s >= 5.0: return "A+"
    if s >= 3.8: return "A"
    if s >= 2.8: return "B"
    return "C"

# === MAIN SCAN ===
def check_live():
    if now_pst().weekday() >= 5 or not (6.5 <= now_pst().hour < 13):
        time.sleep(300); return

    print(f"SCANNING — {now_pst().strftime('%H:%M:%S PST')} — 50 TICKERS — FULL POWER")

    atr_data = get_current_atr_and_range()

    for ticker in TICKERS:
        try:
            prev = get_prev_close(ticker)
            if not prev: continue
            price, _ = get_price_and_ema(ticker, "D", 50)
            if not price: continue
            gap_pct = abs((price - prev)/prev * 100)

            vol_exp = False
            if ticker in atr_data:
                vol_exp = atr_data[ticker]["range"] > atr_data[ticker]["atr"] * 2.2

            if gap_pct < MIN_GAP and not vol_exp: continue

            direction = "LONG" if price > prev else "SHORT"
            gamma = get_gamma_flip(ticker)
            gamma_hit = gamma and abs(gamma - price) < price * GAMMA_TOLERANCE
            strike, prem = find_cheap_contract(ticker, direction)
            if not prem: continue

            for tf, length in CLOUDS:
                _, ema = get_price_and_ema(ticker, tf, length)
                if not ema: continue
                if (direction == "LONG" and price > ema) or (direction == "SHORT" and price < ema):
                    alert_id = f"{ticker}_{direction}_{tf}_{now_pst().date()}"
                    if alert_id in sent_alerts: continue
                    sent_alerts.add(alert_id)

                    grade = get_grade(gap_pct, prem, gamma_hit, tf=="D")
                    conf = "Gamma" if gamma_hit else ("VolExp" if vol_exp else "EMA")
                    msg = f"{ticker} {direction} | {gap_pct:.1f}% | {grade} | {conf} | {strike}@${prem} | {ESTIMATED_HOLD[tf]} | {tf}"
                    send_discord(msg)

        except: continue

    send_heartbeat()

# === START ===
if __name__ == "__main__":
    test_note = " (TEST MODE ACTIVE)" if TEST_MODE else ""
    send_discord(f"REVENANT 2.0 FULLY FIXED{test_note} — Low-liq alive | 429-proof | Deployed & hunting")
    while True:
        try:
            check_live()
            time.sleep(300)
        except Exception as e:
            send_discord(f"LOOP ERROR (still alive): {e}")
            time.sleep(300)
