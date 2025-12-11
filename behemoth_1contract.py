# ================================================================
# BEHEMOTH 1.0 — FINAL STEALTH GOD TIER
# 1 contract · $0.05–$0.10 · 0DTE only · No stop · EOD recap only
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

TICKERS = ["NVDA","TSLA","AMD","SMCI","MSTR","COIN","SOXL","PLTR","AVGO","META","SPY","QQQ"]

alerts_today = set()
daily_pnl = 0.0
current_position = None
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**BEHEMOTH STEALTH** | {now().strftime('%H:%M PST')}\n```{msg}```"})

def safe_aggs(ticker, mult=1, ts="minute", lim=100):
    try:
        return client.get_aggs(ticker, mult, ts,
            from_=int((datetime.now(pst)-timedelta(days=10)).timestamp()*1000),
            to=int(datetime.now(pst).timestamp()*1000), limit=limit)
    except:
        try: return client.get_aggs(ticker, mult, ts, limit=limit)
        except: return []

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

def get_contract(ticker, direction):
    exp = now().strftime('%Y-%m-%d')
    ctype = "call" if "LONG" in direction else "put"
    spot = safe_aggs(ticker,1,"minute",1)[-1].close
    candidates = []
    try:
        contracts = client.list_options_contracts(ticker, contract_type=ctype, expiration_date=exp, limit=200)
        for c in contracts:
            try:
                q = client.get_option_quote(c.ticker)
                if not q or q.ask is None or q.ask > 0.10 or q.bid < 0.05: continue
                strike = float(c.ticker.split(ctype.upper())[-1])
                if abs(strike-spot)/spot <= 0.048 and getattr(q,'open_interest',0) > 200:
                    candidates.append((q.ask, q.open_interest, c.ticker))
            except: continue
    except: pass
    if candidates:
        candidates.sort(key=lambda x: (-x[1], x[0]))
        best = candidates[0]
        return best[2], round(best[0], 3)
    return None, None

def cream_score(ticker, direction, vol_mult, rsi, vwap_dist, big_bonus):
    score = 7.0
    if vol_mult > 4.5: score += 2
    elif vol_mult > 3.2: score += 1.2
    target = 32 if "LONG" in direction else 68
    if abs(rsi-target) < 6: score += 1.8
    if vwap_dist > 0.009: score += 1.2
    if ticker in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI","PLTR"]: score += 1.0
    if big_bonus: score += 3.0
    return min(score, 10)

def check_exit():
    global current_position, daily_pnl
    if not current_position: return
    try:
        q = client.get_option_quote(current_position['contract'])
        bid = q.bid or 0
        entry = current_position['entry']
        if bid >= entry * 2.0:
            pnl = 100 * (bid - entry)
            daily_pnl += pnl
            current_position = None
    except: pass

send("BEHEMOTH 1.0 — STEALTH GOD TIER — LIVE (EOD recap only)")
while True:
    try:
        check_exit()

        if now().weekday() >= 5 or now().hour < 6 or now().hour >= 13:
            time.sleep(300)
            continue

        for t in TICKERS:
            if current_position: break

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

            bias = market_bias()

            if score_l >= 7.8 and price > vwap and rsi < 36 and f"long_{t}" not in alerts_today:
                if bias in ["CALLS_ONLY", "BOTH"]:
                    c,prem = get_contract(t,"LONG")
                    if c and prem <= 0.10:
                        time.sleep(900)
                        try: fill = client.get_option_quote(c).bid or prem
                        except: fill = prem
                        if fill <= 0.
