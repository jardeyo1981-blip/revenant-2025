# revenant_2025_retest_edition.py
# WORKS PERFECTLY ON $29 POLYGON TIER — CATCHES THE RETEST, NOT THE GAP
import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing keys!")
client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50), ("240",50), ("60",50), ("30",50), ("15",50)]
ESTIMATED_HOLD = {"D":"2h–6h", "240":"1h–3h", "60":"30m–1h45m", "30":"15m–45m", "15":"10m–30m"}

MIN_GAP_FOR_PULLBACK = 2.0    # Only look for retests after a real gap happened
MAX_PREMIUM = 1.20            # Cheaper on pullbacks
GAMMA_TOLERANCE = 0.05

sent_alerts = set()
pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant RETEST** | {now_pst().strftime('%H:%M:%S PST')} ```{msg}```"}, timeout=10)
        print(f"ALERT → {msg}")
    except: pass

# PREV CLOSE CACHE
prev_close_cache = {}
last_cache_date = None
def get_prev_close(ticker):
    global prev_close_cache, last_cache_date
    today = now_pst().date()
    if last_cache_date != today:
        prev_close_cache = {}; last_cache_date = today
    if ticker not in prev_close_cache:
        try:
            aggs = client.get_aggs(ticker, 1, "day", limit=5)
            prev_close_cache[ticker] = aggs[-2].close if len(aggs) >= 2 else None
        except: prev_close_cache[ticker] = None
    return prev_close_cache[ticker]

# EMA + HIGH/LOW OF CURRENT PERIOD
def get_price_ema_high_low(ticker, tf, length):
    try:
        mult = {"D":1, "240":4, "60":1, "30":1, "15":1}.get(tf, 1)
        ts = "day" if tf == "D" else "minute"
        days = 730 if tf == "D" else 60
        aggs = client.get_aggs(ticker, mult, ts, (now_pst()-timedelta(days=days)).strftime('%Y-%m-%d'), now_pst().strftime('%Y-%m-%d'), limit=50000)
        if len(aggs) < length: return None, None, None, None
        closes = [a.close for a in aggs]
        highs = [a.high for a in aggs]
        lows = [a.low for a in aggs]
        ema = closes[0]
        k = 2/(length+1)
        for c in closes[1:]: ema = c*k + ema*(1-k)
        return round(closes[-1],4), round(ema,4), max(highs[-10:]), min(lows[-10:])
    except: return None, None, None, None

# GAMMA + CHEAP CONTRACT (low-liq fixed)
def get_gamma_flip(ticker):
    try:
        contracts = client.list_options_contracts(underlying_ticker=ticker, expiration_date_gte=now_pst().strftime('%Y-%m-%d'), expiration_date_lte=(now_pst()+timedelta(days=2)).strftime('%Y-%m-%d'), limit=200)
        strikes = {}
        for c in contracts:
            oi = c.open_interest or 0
            strikes[c.strike_price] = strikes.get(c.strike_price, 0) + oi
        return max(strikes, key=strikes.get) if strikes else None
    except: return None

def find_cheap_contract(ticker, direction):
    try:
        contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'), expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'), limit=100)
        for c in contracts:
            quote = client.get_option_quote(c.ticker)
            if quote:
                price = quote.last_price or quote.bid or quote.ask or 0
                if 0.01 <= price <= MAX_PREMIUM:
                    return c.strike_price, round(price, 2)
    except: pass
    return None, None

def get_grade(gap, prem, gamma_hit, daily):
    s = gap
    if daily: s *= 2.2
    if gamma_hit: s *= 1.5
    if prem <= 0.7: s *= 1.3
    if s >= 7.0: return "A++"
    if s >= 5.5: return "A+"
    if s >= 4.0: return "A"
    if s >= 2.5: return "B"
    return "C"

# MAIN LOOP — RETEST EDITION
send("REVENANT RETEST EDITION — LIVE — $29 tier ready — Hunting pullbacks")
while True:
    try:
        if now_pst().weekday() >= 5 or not (6.5 <= now_pst().hour < 13):
            time.sleep(300); continue

        print(f"SCANNING RETESTS — {now_pst().strftime('%H:%M:%S PST')} — 50 TICKERS")

        for ticker in TICKERS:
            prev = get_prev_close(ticker)
            if not prev: continue
            price, ema_daily, _, _ = get_price_ema_high_low(ticker, "D", 50)
            if not price or not ema_daily: continue

            # Only look for retests after a meaningful gap
            gap_pct = abs((price - prev) / prev * 100)
            if gap_pct < MIN_GAP_FOR_PULLBACK: continue

            direction = "LONG" if price > prev else "SHORT"
            gamma = get_gamma_flip(ticker)
            gamma_hit = gamma and abs(gamma - price) < price * GAMMA_TOLERANCE
            strike, prem = find_cheap_contract(ticker, direction)
            if not prem: continue

            # Check all clouds for pullback to EMA
            for tf, length in CLOUDS:
                price_tf, ema_tf, high_tf, low_tf = get_price_ema_high_low(ticker, tf, length)
                if not ema_tf: continue

                retest_long = direction == "LONG" and low_tf <= ema_tf <= price_tf
                retest_short = direction == "SHORT" and high_tf >= ema_tf >= price_tf

                if retest_long or retest_short:
                    alert_id = f"{ticker}_{direction}_retest_{tf}_{now_pst().date()}"
                    if alert_id in sent_alerts: continue
                    sent_alerts.add(alert_id)

                    grade = get_grade(gap_pct, prem, gamma_hit, tf=="D")
                    conf = "Gamma" if gamma_hit else "Retest"
                    msg = f"{ticker} {direction} RETEST | {gap_pct:.1f}% gap | {grade} | {conf} | {strike}@${prem} | {ESTIMATED_HOLD[tf]} | {tf}"
                    send(msg)

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
