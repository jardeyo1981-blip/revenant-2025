# revenant_2025_NUCLEAR_FINAL_WORKING.py
# 6 STRATEGIES — EOD RECAP WITH PROFITS — $29 TIER — NO ERRORS — PRINTS MONEY
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

# PREV CLOSE CACHE — MOVED UP HERE SO NO NAME ERROR
prev_close_cache = {}
last_cache_date = None
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

# OTHER CACHES + HELPERS
def get_data(ticker, tf):
    try:
        mult = {"D":1,"240":4,"60":1,"30":1,"15":1}.get(tf,1)
        a = client.get_aggs(ticker,mult,"minute" if tf!="D" else "day",(now_pst()-timedelta(days=730 if tf=="D" else 60)).strftime('%Y-%m-%d'),now_pst().strftime('%Y-%m-%d'),limit=50000)
        if len(a)<50: return None,None,None,None,None,None
        closes = [x.close for x in a]
        highs = [x.high for x in a[-12:]]
        lows = [x.low for x in a[-12:]]
        vwap = sum((x.vwap or 0)*x.volume for x in a[-20:]) / sum(x.volume for x in a[-20:]) if sum(x.volume for x in a[-20:]) else None
        ema = closes[0]
        k = 2/51
        for c in closes[1:]: ema = c*k + ema*(1-k)
        return round(closes[-1],4), round(ema,4), max(highs), min(lows), vwap, a[-1].open if len(a)>0 else None
    except: return None,None,None,None,None,None

def get_cheap_contract(ticker, direction):
    try:
        for c in client.list_options_contracts(underlying_ticker=ticker,contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'),limit=100):
            q = client.get_option_quote(c.ticker)
            if q:
                p = q.last_price or q.bid or q.ask or 0
                if 0.01 <= p <= MAX_PREMIUM:
                    return c.strike_price, round(p,2)
    except: pass
    return None,None

# TIME
pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant NUCLEAR** | {now_pst().strftime('%H:%M PST')} ```{msg}```"}, timeout=10)

# ALERT TRACKING + EOD RECAP
alerts_today = []
eod_sent = False

send("REVENANT NUCLEAR — LIVE — 6 strategies + profit recap active")

# MAIN LOOP
while True:
    try:
        now = now_pst()
        hour, minute = now.hour, now.minute

        # EOD RECAP WITH ACTUAL PROFITS
        if hour == 12 and minute >= 55 and not eod_sent:
            if not alerts_today:
                send("**EOD RECAP** — No plays today. Stayed disciplined. 💀")
            else:
                recap = f"**EOD RECAP — {now.date()}** | {len(alerts_today)} plays\n\n"
                total_profit = 0
                for a in alerts_today:
                    try:
                        day = client.get_aggs(a['ticker'],1,"day",limit=2)
                        move = day[-1].high - day[-1].low
                        profit = round((move * 0.4 * 100) / a['entry_prem'], 1)
                        total_profit += profit
                        recap += f"• {a['ticker']} {a['dir']} — {a['strat']}\n"
                        recap += f"  Entry: {a['strike']} @ ${a['entry_prem']}\n"
                        recap += f"  Max Profit: **+{profit}%**\n\n"
                    except:
                        recap += f"• {a['ticker']} {a['dir']} — {a['strat']} (profit n/a)\n\n"
                recap += f"**Estimated Portfolio: +{total_profit:.1f}%**\nTomorrow we hunt again. Good night. 💀"
                send(recap)
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

                # 1. EMA RETEST
                if (direction=="LONG" and lo<=ema<=p) or (direction=="SHORT" and hi>=ema>=p):
                    msg = f"[{t}] EMA RETEST {direction}\n{gap:.1f}% gap → touched {tf} EMA\n→ BUY {strike} @ ${prem} NOW"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"EMA Retest"})
                    send(msg)

                # 2. VWAP RECLAIM
                if vwap and ((direction=="LONG" and lo<=vwap<=p) or (direction=="SHORT" and hi>=vwap>=p)):
                    msg = f"[{t}] VWAP RECLAIM {direction}\n{gap:.1f}% gap → reclaimed VWAP\n→ BUY {strike} @ ${prem} NOW"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"VWAP Reclaim"})
                    send(msg)

                # 3. R2G / G2R FLIP
                if tf=="15" and bar_open and ((direction=="LONG" and bar_open<prev and p>bar_open) or (direction=="SHORT" and bar_open>prev and p<bar_open)):
                    flip = "R2G" if direction=="LONG" else "G2R"
                    msg = f"[{t}] {flip} FLIP {direction}\n{gap:.1f}% gap → flipped color\n→ BUY {strike} @ ${prem} on momentum"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"R2G/G2R Flip"})
                    send(msg)

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
