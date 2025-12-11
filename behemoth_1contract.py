# ================================================================
# BEHEMOTH 1.0 — 1 CONTRACT SNIPER (runs alongside Revenant)
# 7.8+ CREAM · Auto-scalp · 2× or –55% · 15-min delay · ONE CONTRACT ONLY
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
current_position = None
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**🟢 BEHEMOTH 1-CONTRACT** | {now().strftime('%H:%M PST')}\n```{msg}```"})

def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100):
    try:
        return client.get_aggs(ticker, multiplier, timespan,
            from_=int((datetime.now(pst)-timedelta(days=10)).timestamp()*1000),
            to=int(datetime.now(pst).timestamp()*1000), limit=limit)
    except:
        try: return client.get_aggs(ticker, multiplier, timespan, limit=limit)
        except: return []

# ONLY RUN DURING REGULAR MARKET HOURS (6:30 AM – 1:00 PM PST)
def is_market_hours():
    n = now()
    if n.weekday() >= 5:                  # Saturday or Sunday
        return False
    hour = n.hour
    minute = n.minute
    if hour < 6 or hour > 13:             # outside 6–13
        return False
    if hour == 6 and minute < 30:         # before 6:30
        return False
    if hour == 13 and minute > 0:         # after 1:00 PM
        return False
    return True

def market_bias():
    vix = safe_aggs("VIX",1,"day",3)
    vix1d = safe_aggs("VIX1D",1,"day",3)
    if len(vix)<2 or len(vix1d)<2: return "BOTH"
    change = (vix1d[-1].close / vix1d[-2].close - 1)
    if vix[-1].close < 22 or change < -0.08: return "CALLS_ONLY"
    elif vix[-1].close > 26 or change > 0.12: return "PUTS_ONLY"
    else: return "BOTH"

def mtf_air_gap(ticker):
    try:
        bars15 = safe_aggs(ticker,15,"minute",20)
        if len(bars15)<2: return 0, False
        prev, curr = bars15[-2], bars15[-1]
        price = safe_aggs(ticker,1,"minute",1)[-1].close
        gap_size = abs(price - (prev.high if price>prev.high else prev.low))
        prev_range = prev.high-prev.low
        bonus = gap_size > prev_range*0.5
        if price > prev.high and curr.low > prev.high: return 1, bonus
        if price < prev.low and curr.high < prev.low: return -1, bonus
        return 0, False
    except: return 0, False

def get_expiration_days(ticker):
    wd = now().weekday()
    if ticker in INDEX: return [0] if wd<=1 else []
    if wd<=1: return [4,5]
    if wd<=3: return [1,2,3]
    return [1,2,3,4,5]

def get_contract(ticker, direction):
    days = get_expiration_days(ticker)
    if not days: return None,None,None
    ctype = "call" if "LONG" in direction else "put"
    spot = safe_aggs(ticker,1,"minute",1)[-1].close
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

def cream_score(ticker, direction, vol_mult, rsi, vwap_dist, big_bonus):
    score = 7.0
    if get_vix1d() >= 24: score += 3
    if vol_mult>4.5: score += 2
    elif vol_mult>3.2: score += 1.2
    target = 32 if "LONG" in direction else 68
    if abs(rsi-target)<6: score += 1.8
    if vwap_dist>0.009: score += 1.2
    if ticker in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI","PLTR"]: score += 1.0
    if big_bonus: score += 3.0
    return min(score,10)

def check_exit():
    global current_position
    if not current_position: return
    try:
        q = client.get_option_quote(current_position['contract'])
        bid = q.bid or 0
        entry = current_position['entry']
        ticker = current_position['ticker']

        if bid >= entry * 2.0:
            pnl = 100 * (bid - entry)
            send(f"BEHEMOTH EXIT {ticker} +100% @ ${bid:.2f} | P&L ${pnl:.0f}")
            current_position = None
            return
        if bid <= entry * 0.45:
            pnl = 100 * (bid - entry)
            send(f"BEHEMOTH STOP {ticker} –55% @ ${bid:.2f} | P&L ${pnl:.0f}")
            current_position = None
    except: pass

send("BEHEMOTH 1.0 — 1 CONTRACT SNIPER — LIVE")
while True:
    try:
        check_exit()

        if time.time() - last_heartbeat >= 300:
            bias = market_bias()
            print(f"BEHEMOTH {now().strftime('%H:%M PST')} | VIX {get_vix1d():.1f} | BIAS: {bias}")
            last_heartbeat = time.time()

        bias = market_bias()

        for t in TICKERS:
            if current_position: continue

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

            if score_l >= 7.8 and price > vwap and rsi < 36 and f"long_{t}" not in alerts_today:
                if bias in ["CALLS_ONLY", "BOTH"]:
                    c,prem,dte = get_contract(t,"LONG")
                    if c:
                        alerts_today.add(f"long_{t}")
                        time.sleep(900)
                        try: fill = client.get_option_quote(c).bid or prem
                        except: fill = prem
                        if fill <= 0.35:
                            current_position = {'ticker':t,'contract':c,'entry':fill}
                            send(f"BEHEMOTH CALL {t} {dte} ★CREAM {score_l:.1f}★ [1 contract]\n{c} filled ${fill:.2f}\nTarget 2× or –55%")

            if score_s >= 7.8 and price < vwap and rsi > 64 and f"short_{t}" not in alerts_today:
                if bias in ["PUTS_ONLY", "BOTH"]:
                    c,prem,dte = get_contract(t,"SHORT")
                    if c:
                        alerts_today.add(f"short_{t}")
                        time.sleep(900)
                        try: fill = client.get_option_quote(c).bid or prem
                        except: fill = prem
                        if fill <= 0.35:
                            current_position = {'ticker':t,'contract':c,'entry':fill}
                            send(f"BEHEMOTH PUT {t} {dte} ★CREAM {score_s:.1f}★ [1 contract]\n{c} filled ${fill:.2f}\nTarget 2× or –55%")

        if now().hour >= 13 and not eod_sent:
            send(f"BEHEMOTH EOD — {len(alerts_today)} scalps today")
            eod_sent = True
        if now().hour == 1:
            alerts_today.clear(); current_position = None; eod_sent = False

        time.sleep(60)
    except Exception as e:
        send(f"BEHEMOTH ERROR: {str(e)[:100]}")
        time.sleep(60)
