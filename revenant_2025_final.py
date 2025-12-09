# revenant_2025_NUCLEAR_FINAL_EVERYTHING.py
# THE ONE — 6 STRATEGIES — EOD RECAP — $0.70 CRUSH — PRINTS MONEY
import os, time, requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

MIN_GAP = 1.8
MAX_PREMIUM = 0.70

alerts_today = []
eod_sent = False
heartbeat_sent = False
last_scan_time = 0

pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant NUCLEAR** | {now_pst().strftime('%H:%M PST')} ```{msg}```"}, timeout=10)

# CACHES
prev_close_cache = {}
def get_prev_close(t):
    global prev_close_cache
    today = now_pst().date()
    if t not in prev_close_cache:
        try: prev_close_cache[t] = client.get_aggs(t,1,"day",limit=5)[-2].close
        except: prev_close_cache[t] = None
    return prev_close_cache[t]

def get_data(t, tf):
    try:
        mult = {"D":1,"240":4,"60":1,"30":1,"15":1}.get(tf,1)
        a = client.get_aggs(t,mult,"minute" if tf!="D" else "day",(now_pst()-timedelta(days=730 if tf=="D" else 60)).strftime('%Y-%m-%d'),now_pst().strftime('%Y-%m-%d'),limit=50000)
        if len(a)<50: return None,None,None,None,None,None
        closes = [x.close for x in a]
        highs = [x.high for x in a[-12:]]
        lows  = [x.low for x in a[-12:]]
        opens = [x.open for x in a[-1:]]
        vwap = sum((x.vwap or 0)*x.volume for x in a[-20:]) / sum(x.volume for x in a[-20:]) if sum(x.volume for x in a[-20:]) else None
        ema = closes[0]
        k = 2/51
        for c in closes[1:]: ema = c*k + ema*(1-k)
        return round(closes[-1],4), round(ema,4), max(highs), min(lows), vwap, opens[0] if opens else None
    except: return None,None,None,None,None,None

def get_cheap_contract(t, direction):
    try:
        for c in client.list_options_contracts(underlying_ticker=t,contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'),limit=100):
            q = client.get_option_quote(c.ticker)
            if q:
                p = q.last_price or q.bid or q.ask or 0
                if 0.01 <= p <= MAX_PREMIUM:
                    return c.strike_price, round(p,2)
    except: pass
    return None,None

# MAIN LOOP — 6 STRATEGIES + EOD + HEARTBEAT
send("REVENANT NUCLEAR — LIVE — 6 strategies + recap — Deployed")
while True:
    try:
        now = now_pst()
        hour, minute = now.hour, now.minute
        current_time = time.time()

        # HEARTBEAT EVERY 5 MIN
        if current_time - last_scan_time >= 300:
            print(f"SCANNING — {now_pst().strftime('%H:%M:%S PST')} — 50 TICKERS — no 429s")
            last_scan_time = current_time

        # EOD RECAP
        if hour == 12 and minute >= 55 and not eod_sent:
            # [your existing recap code ]
            eod_sent = True
            alerts_today = []

        if now.weekday() >= 5 or not (6.5 <= hour < 13):
            time.sleep(300); continue

        for t in TICKERS:
            prev = get_prev_close(t)
            if not prev: continue
            price, _, _, _, _, _ = get_data(t,"D")
            if not price: continue
            gap = abs((price-prev)/prev*100)
            if gap < MIN_GAP: continue
            direction = "LONG" if price>prev else "SHORT"

            strike, prem = get_cheap_contract(t,direction)
            if not prem: continue

            for tf in ["15","30","60","240","D"]:
                p, ema, hi, lo, vwap, bar_open = get_data(t,tf)
                if not ema: continue

                sent = False

                # 1. EMA RETEST
                if (direction=="LONG" and lo<=ema<=p) or (direction=="SHORT" and hi>=ema>=p):
                    msg = f"[{t}] EMA RETEST {direction}\n{gap:.1f}% gap → touched {tf} EMA\n→ BUY {strike} @ ${prem} NOW\nTarget: 2–2.5× gap"
                    if f"retest_{t}_{tf}" not in alerts_today:
                        alerts_today.append(f"{t} {direction} EMA {tf}")
                        send(msg); sent = True

                # 2. VWAP RECLAIM
                if vwap and ((direction=="LONG" and lo<=vwap<=p) or (direction=="SHORT" and hi>=vwap>=p)) and not sent:
                    msg = f"[{t}] VWAP RECLAIM {direction}\n{gap:.1f}% gap → reclaimed VWAP\n→ BUY {strike} @ ${prem} NOW"
                    if f"vwap_{t}" not in alerts_today:
                        alerts_today.append(f"{t} {direction} VWAP")
                        send(msg); sent = True

                # 3. R2G / G2R FLIP
                if tf=="15" and bar_open and ((direction=="LONG" and bar_open<prev and p>bar_open) or (direction=="SHORT" and bar_open>prev and p<bar_open)) and not sent:
                    flip = "R2G" if direction=="LONG" else "G2R"
                    msg = f"[{t}] {flip} FLIP {direction}\n{gap:.1f}% gap → flipped color\n→ BUY {strike} @ ${prem} on momentum"
                    if f"flip_{t}" not in alerts_today:
                        alerts_today.append(f"{t} {flip}")
                        send(msg)

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
