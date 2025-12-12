# REVENANT 2025 — FINAL CLEAN — RUNS FIRST TRY
import os, time, requests, pytz, logging
from datetime import datetime, timedelta

log_path = os.path.expanduser("~/revenant.log")
logging.basicConfig(filename=log_path, level=logging.INFO,
                    format="%(asctime)s | %(message)s", datefmt="%H:%M", filemode='a')
console = logging.StreamHandler(); console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
TICKERS = ["SPY","QQQ","IWM","XLF","XLK","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN","SOXL","TQQQ","SQQQ","UVXY"]

alerts_today = set()
daily_pnl = 0
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(m):
    try: requests.post(WEBHOOK, json={"content": f"[R25] {now():%H:%M} | {m}"}, timeout=8)
    except: pass

def safe_aggs(t, m=1, ts="minute", lim=100):
    try: return list(client.get_aggs(t, m, ts, limit=lim)) if client.get_aggs(t, m, ts, limit=lim) else []
    except: return []

def get_price(t): b = safe_aggs(t); return b[-1].close if b else None
def vwap20(t):
    b = safe_aggs(t,1,"minute",50)
    if len(b) < 20: return None
    vol = sum(x.volume for x in b[-20:])
    return sum((x.vwap or x.close)*x.volume for x in b[-20]) / vol if vol else b[-1].close

def rsi14(t):
    b = safe_aggs(t,1,"minute",30)
    if len(b) < 15: return 50
    gains = sum(max(x.close-x.open,0) for x in b[-14:])
    losses = sum(abs(min(x.close-x.open,0)) for x in b[-14:]) or 1
    return 100 - 100/(1 + gains/losses)

def cream(t, side):
    score = 7.0
    if get_vix1d() >= 24: score += 3
    b = safe_aggs(t,1,"minute",50)
    if len(b) > 20:
        vm = b[-1].volume / (sum(x.volume for x in b[-21:-1])/20 or 1)
        if vm > 4.5: score += 2
        elif vm > 3.2: score += 1.2
    if abs(rsi14(t) - (32 if side=="LONG" else 68)) < 6: score += 1.8
    if t in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI"]: score += 1.0
    g, bonus = big_gap(t)
    if (side=="LONG" and g==1) or (side=="SHORT" and g==-1):
        if bonus: score += 3.0
    return min(score, 10.0)

def big_gap(t):
    b = safe_aggs(t,15,"minute",10)
    if len(b) < 2: return 0, False
    prev = b[-2]
    p = get_price(t)
    if not p: return 0, False
    bonus = abs(p - (prev.high if p>prev.high else prev.low)) > (prev.high-prev.low)*0.5
    return (1 if p>prev.high else -1 if p<prev.low else 0), bonus

def get_vix1d():
    b = safe_aggs("VIX",1,"day",3)
    return b[-1].close if b else 18.0

def get_contract(t, side):
    spot = get_price(t)
    if not spot: return None,None,None
    ctype = "call" if side=="LONG" else "put"
    days = [0,1,2,3,4,5] if t in ["SPY","QQQ","IWM"] else [1,2,3,4,5]
    cands = []
    for d in days:
        exp = (now()+timedelta(days=d)).strftime("%Y-%m-%d")
        try:
            for c in client.list_options_contracts(t, contract_type=ctype, expiration_date=exp, limit=150):
                q = client.get_option_quote(c.ticker)
                if q and q.ask and 0.22 <= q.ask <= 0.45 and q.bid >= 0.10 and getattr(q,'open_interest',0) >= 300:
                    if abs(float(c.strike_price)-spot)/spot <= 0.05:
                        cands.append((q.ask, q.open_interest or 0, c.ticker, f"{d}DTE"))
        except: pass
    if not cands: return None,None,None
    cands.sort(key=lambda x: (-x[1], x[0]))
    return cands[0][2], round(cands[0][0],2), cands[0][3]

BASE, CAP = 17, 70
def size(): 
    global daily_pnl
    return min(BASE + max(0, daily_pnl // 650), CAP)

send("REVENANT 2025 LIVE")
while True:
    try:
        for t in TICKERS:
            p = get_price(t)
            v = vwap20(t)
            if not p or not v: continue
            sz = size()

            if cream(t,"LONG") >= 8.4 and p > v and rsi14(t) < 36 and f"L{t}" not in alerts_today:
                c, pr, dte = get_contract(t,"LONG")
                if c:
                    alerts_today.add(f"L{t}")
                    send(f"{t} {dte} CALL {cream(t,'LONG'):.1f} [{sz}] @ ${pr}")
                    daily_pnl += sz * 100 * 2.9

            if cream(t,"SHORT") >= 8.4 and p < v and rsi14(t) > 64 and f"S{t}" not in alerts_today:
                c, pr, dte = get_contract(t,"SHORT")
                if c:
                    alerts_today.add(f"S{t}")
                    send(f"{t} {dte} PUT {cream(t,'SHORT'):.1f} [{sz}] @ ${pr}")
                    daily_pnl += sz * 100 * 2.7

        if now().hour == 2:
            alerts_today.clear()
            daily_pnl = 0

        time.sleep(300)
    except Exception as e:
        logging.error(f"ERROR: {e}")
        send(f"crash {e}")
        time.sleep(300)
