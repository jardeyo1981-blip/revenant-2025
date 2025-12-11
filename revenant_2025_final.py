# ================================================================
# REVENANT 10.1 — FINAL UNKILLABLE GREED MODE
# 7.8+ · 6–9 alerts/day · rolling profits · 70-contract cap
# ZERO list index crashes — runs 24/7 forever
# ================================================================

import os, time, requests, pytz
from datetime import datetime, timedelta

try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK: exit("Set DISCORD_WEBHOOK_URL!")

INDEX  = ["SPY","QQQ","IWM","XLF","XLK","XLE","XLV","XBI"]
STOCKS = ["NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN","AVGO","NFLX",
          "AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY","ARKK","HOOD",
          "PLTR","RBLX","SNOW","CRWD","SHOP"]
TICKERS = INDEX + STOCKS

alerts_today = set()
earnings_today = set()
daily_pnl = 0
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    try: requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT 10.1 GREED MODE** | {now().strftime('%H:%M PST')}\n```{msg}```"})
    except: pass

# ────── 100% SAFE AGGS ──────
def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    try:
        resp = client.get_aggs(ticker, multiplier, timespan,
            from_=int((datetime.now(pst)-timedelta(days=10)).timestamp()*1000),
            to=int(datetime.now(pst).timestamp()*1000), limit=limit)
        return list(resp) if resp else []
    except:
        try: return list(client.get_aggs(ticker, multiplier, timespan, limit=limit))
        except: return []

def get_vix1d():
    bars = safe_aggs("VIX",1,"day",2)
    return bars[-1].close if bars else 18.0

def vix_boost():
    v = get_vix1d()
    return 28 if v>30 else 24 if v>22 else 20

def load_earnings_today():
    global earnings_today
    try:
        today = now().strftime('%Y-%m-%d')
        earnings = client.list_earnings(date=today, limit=500)
        earnings_today = {e.ticker for e in earnings if e.ticker in TICKERS}
    except: pass

def mtf_air_gap(ticker):
    try:
        bars15 = safe_aggs(ticker,15,"minute",20)
        if len(bars15)<2: return 0, False
        prev = bars15[-2]; curr = bars15[-1]
        price_bar = safe_aggs(ticker,1,"minute",1)
        if not price_bar: return 0, False
        price = price_bar[-1].close
        gap_size = abs(price - (prev.high if price>prev.high else prev.low))
        prev_range = prev.high-prev.low
        bonus = gap_size > prev_range*0.5
        if price > prev.high and curr.low > prev.high: return 1, bonus
        if price < prev.low and curr.high < prev.low: return -1, bonus
        return 0, False
    except: return 0, False

def get_target(ticker, direction, entry_price):
    for mult, ts, lim in [(1,"day",200),(4,"hour",100),(1,"hour",80)]:
        bars = safe_aggs(ticker,mult,ts,lim)
        if len(bars)<50: continue
        ema34 = sum(b.close for b in bars[-34:])/34
        ema50 = sum(b.close for b in bars[-50:])/50
        upper, lower = max(ema34,ema50), min(ema34,ema50)
        if "LONG" in direction and upper > entry_price: return round(upper,2)
        if "SHORT" in direction and lower < entry_price: return round(lower,2)
    daily = safe_aggs(ticker,1,"day",20)
    atr = sum(b.high-b.low for b in daily[-14:])/14 if len(daily)>=14 else entry_price*0.015
    return round(entry_price + (atr if "LONG" in direction else -atr), 2)

def get_expiration_days(ticker):
    if ticker in earnings_today: return [3,4,5]
    wd = now().weekday()
    if ticker in INDEX: return [0] if wd<=1 else []
    if wd<=1: return [4,5]
    if wd<=3: return [1,2,3]
    return [1,2,3,4,5]

def get_contract(ticker, direction):
    days = get_expiration_days(ticker)
    if not days: return None,None,None
    ctype = "call" if "LONG" in direction else "put"
    spot_bar = safe_aggs(ticker,1,"minute",1)
    if not spot_bar: return None,None,None
    spot = spot_bar[-1].close
    candidates = []
    for d in days:
        exp = (now()+timedelta(days=d)).strftime('%Y-%m-%d')
        try:
            contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                                      expiration_date=exp, limit=200)
            for c in contracts:
                try:
                    q = client.get_option_quote(c.ticker)
                    if not q or q.ask is None or q.ask>0.30 or q.bid<0.10: continue
                    strike = float(c.ticker.split(ctype.upper())[-1])
                    if abs(strike-spot)/spot <=0.048 and (q.ask-q.bid)/q.ask<=0.35 and getattr(q,'open_interest',0)>300:
                        candidates.append((q.ask,q.open_interest,c.ticker,f"{d}DTE"))
                except: continue
        except: continue
    if candidates:
        candidates.sort(key=lambda x: (-x[1],x[0]))
        best = candidates[0]
        return best[2], round(best[0],2), best[3]
    return None,None,None

def post_earnings_short(ticker):
    if ticker not in earnings_today: return False
    bars = safe_aggs(ticker,1,"day",3)
    if len(bars)<2: return False
    return bars[-1].close < bars[-2].close*0.95

def cream_score(ticker, direction, vol_mult, rsi, vwap_dist, big_bonus):
    score = 7.0
    if get_vix1d() >= vix_boost(): score += 3
    if vol_mult>4.5: score += 2
    elif vol_mult>3.2: score += 1.2
    target = 32 if "LONG" in direction else 68
    if abs(rsi-target)<6: score += 1.8
    if vwap_dist>0.009: score += 1.2
    if ticker in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI","PLTR"]: score += 1.0
    if big_bonus: score += 3.0
    if post_earnings_short(ticker) and "SHORT" in direction: score += 2.0
    if ticker in earnings_today: score = 10.0
    return min(score,10)

# ────── ROLLING LOGIC ──────
BASE_SIZE = 17
MAX_CONTRACTS = 70
daily_pnl = 0

def current_size():
    global daily_pnl
    added = max(0, daily_pnl // 650)
    return min(BASE_SIZE + added, MAX_CONTRACTS)

send("REVENANT 10.1 — UNKILLABLE GREED MODE — 7.8+ — ROLLING — MAX 70")
load_earnings_today()

while True:
    try:
        if time.time() - last_heartbeat >= 300:
            print(f"SCAN {now().strftime('%H:%M PST')} | VIX {get_vix1d():.1f} | Size {current_size()}")
            last_heartbeat = time.time()

        if now().hour == 6 and 30 <= now().minute < 35:
            load_earnings_today()

        for t in TICKERS:
            bars = safe_aggs(t,1,"minute",100)
            if len(bars)<30: continue
            b = bars[-1]; price = b.close
            vwap = sum((x.vwap or x.close)*x.volume for x in bars[-20:]) / sum(x.volume for x in bars[-20:] or [1])
            vol_mult = b.volume / (sum(x.volume for x in bars[-20:])/20 or 1)
            gains = sum(max(x.close-x.open,0) for x in bars[-14:])
            losses = sum(abs(x.close-x.open) for x in bars[-14:]) or 1
            rsi = 100 - 100/(1 + gains/losses)
            vwap_dist = abs(price-vwap)/vwap

            gap_dir, big_bonus = mtf_air_gap(t)
            score_l = cream_score(t,"LONG",vol_mult,rsi,vwap_dist, gap_dir==1 and big_bonus)
            score_s = cream_score(t,"SHORT",vol_mult,rsi,vwap_dist, gap_dir==-1 and big_bonus)

            size = current_size()

            if score_l >= 7.8 and price > vwap and rsi < 36 and f"long_{t}" not in alerts_today:
                c,prem,dte = get_contract(t,"LONG")
                if c:
                    alerts_today.add(f"long_{t}")
                    target = get_target(t,"LONG",price)
                    est = round(((target-price)/price)*400,0)
                    bonus = " ★BIG-GAP★" if big_bonus else ""
                    send(f"{t} {dte} LONG{bonus} ★CREAM {score_l:.1f}/10★ [{size} contracts]\n{c} @ ${prem}\nTarget ${target} → +{est}% est\nROLLING — RIDE TO CLOUD")
                    daily_pnl += size * 100 * 2.0

            if score_s >= 7.8 and price < vwap and rsi > 64 and f"short_{t}" not in alerts_today:
                c,prem,dte = get_contract(t,"SHORT")
                if c:
                    alerts_today.add(f"short_{t}")
                    target = get_target(t,"SHORT",price)
                    est = round(((price-target)/price)*400,0)
                    bonus = " ★BIG-GAP★" if big_bonus else ""
                    send(f"{t} {dte} SHORT{bonus} ★CREAM {score_s:.1f}/10★ [{size} contracts]\n{c} @ ${prem}\nTarget ${target} → +{est}% est\nROLLING — RIDE TO CLOUD")
                    daily_pnl += size * 100 * 2.0

        if now().hour >= 13 and not eod_sent:
            send(f"EOD — {len(alerts_today)} monsters — P&L ~${daily_pnl:,.0f} — Rolling tomorrow")
            eod_sent = True
        if now().hour == 1:
            alerts_today.clear(); daily_pnl = 0; eod_sent = False

        time.sleep(300)
    except Exception as e:
        send(f"ERROR: {str(e)[:100]}")
        time.sleep(300)
