# revenant_2025_retest_clean_final.py
# FINAL — $29 TIER PROOF — PURE RETEST + PREMIUM CRUSH — NO GRADING
import os, time, requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50), ("240",50), ("60",50), ("30",50), ("15",50)]
ESTIMATED_HOLD = {"D":"2h–6h", "240":"1h–3h", "60":"30m–1h45m", "30":"15m–45m", "15":"10m–30m"}

MIN_GAP = 2.0              # Must have gapped hard first
MAX_PREMIUM_NOW = 0.95     # Only buy when premium is truly crushed
GAMMA_TOLERANCE = 0.05

sent_alerts = set()
pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant RETEST** | {now_pst().strftime('%H:%M:%S PST')} ```{msg}```"}, timeout=10)

# PREV CLOSE CACHE
prev_close_cache = {}
def get_prev_close(ticker):
    global prev_close_cache
    today = now_pst().date()
    if ticker not in prev_close_cache:
        try:
            aggs = client.get_aggs(ticker, 1, "day", limit=5)
            prev_close_cache[ticker] = aggs[-2].close
        except: prev_close_cache[ticker] = None
    return prev_close_cache[ticker]

# PRICE + EMA + HIGH/LOW
def get_data(ticker, tf, length):
    try:
        mult = {"D":1, "240":4, "60":1, "30":1, "15":1}.get(tf, 1)
        ts = "day" if tf == "D" else "minute"
        days = 730 if tf == "D" else 60
        aggs = client.get_aggs(ticker, mult, ts, (now_pst()-timedelta(days=days)).strftime('%Y-%m-%d'), now_pst().strftime('%Y-%m-%d'), limit=50000)
        if len(aggs) < length: return None,None,None,None
        closes = [a.close for a in aggs]
        highs = [a.high for a in aggs[-10:]]
        lows = [a.low for a in aggs[-10:]]
        ema = closes[0]
        k = 2/(length+1)
        for c in closes[1:]: ema = c*k + ema*(1-k)
        return round(closes[-1],4), round(ema,4), max(highs), min(lows)
    except: return None,None,None,None

# CURRENT CHEAP CONTRACT (REAL PRICE RIGHT NOW — DELAYED)
def get_current_premium(ticker, direction):
    try:
        contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'), expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'), limit=100)
        for c in contracts:
            q = client.get_option_quote(c.ticker)
            if q:
                price = q.last_price or q.bid or q.ask or 0
                if 0.01 <= price <= MAX_PREMIUM_NOW:
                    return c.strike_price, round(price, 2)
    except: pass
    return None, None

# MAIN LOOP — PURE RETEST + CRUSHED PREMIUM
send("REVENANT RETEST — LIVE — $29 tier proof — Waiting for premium crush")
while True:
    try:
        if now_pst().weekday() >= 5 or not (6.5 <= now_pst().hour < 13):
            time.sleep(300); continue

        print(f"SCANNING RETESTS — {now_pst().strftime('%H:%M:%S PST')}")

        for ticker in TICKERS:
            prev = get_prev_close(ticker)
            if not prev: continue
            price, _, _, _ = get_data(ticker, "D", 50)
            if not price: continue

            gap_pct = abs((price - prev) / prev * 100)
            if gap_pct < MIN_GAP: continue

            direction = "LONG" if price > prev else "SHORT"

            for tf, length in CLOUDS:
                price_tf, ema_tf, high_tf, low_tf = get_data(ticker, tf, length)
                if not ema_tf: continue

                retest_long  = direction == "LONG"  and low_tf  <= ema_tf <= price_tf
                retest_short = direction == "SHORT" and high_tf >= ema_tf >= price_tf

                if not (retest_long or retest_short): continue

                strike, prem = get_current_premium(ticker, direction)
                if not prem: continue  # ← ONLY fires when premium is ACTUALLY crushed

                alert_id = f"{ticker}_{direction}_retest_{tf}_{now_pst().date()}"
                if alert_id in sent_alerts: continue
                sent_alerts.add(alert_id)

                msg = f"{ticker} {direction} RETEST\n" \
                      f"{gap_pct:.1f}% gap → pulled back to {tf} EMA\n" \
                      f"{strike} @ ${prem} ← PREMIUM CRUSHED\n" \
                      f"BUY NOW — second leg incoming\n" \
                      f"Hold: {ESTIMATED_HOLD[tf]}"
                send(msg)

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
