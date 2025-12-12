# REVENANT 11 – CREAM 8.4 / MIN $0.22 / LOGS TO REPO ROOT
# Drop this file anywhere in your repo → log always ends up in repo root

import os, time, requests, pytz, logging
from datetime import datetime, timedelta

# ==================== AUTO LOG TO REPO ROOT ====================
def get_repo_root():
    current = os.path.abspath(os.path.dirname(__file__))
    while current != os.path.dirname(current):  # stop at filesystem root
        if os.path.isdir(os.path.join(current, '.git')):
            return current
        current = os.path.dirname(current)
    return os.path.abspath(os.path.dirname(__file__))  # fallback

log_path = os.path.join(get_repo_root(), "revenant.log")

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%m-%d %H:%M:%S",
    filemode='a'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%H:%M"))
logging.getLogger().addHandler(console)
logging.info("=== REVENANT 11 STARTED – CREAM 8.4 – LOGGING TO REPO ROOT ===")
logging.info(f"Log file: {log_path}")

# ==================== CONFIG & CLIENT ====================
try:
    from polygon import RESTClient
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except:
    from polygon.rest import RESTClient as OldClient
    client = OldClient(api_key=os.getenv("MASSIVE_API_KEY"))

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not WEBHOOK:
    logging.error("DISCORD_WEBHOOK_URL not set")
    exit(1)

TICKERS = ["SPY","QQQ","IWM","XLF","XLK","XLE","XLV","XBI","NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN","AVGO","NFLX","AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY","ARKK","HOOD","PLTR","RBLX","SNOW","CRWD","SHOP"]

alerts_today = set()
daily_pnl = 0
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    try:
        requests.post(WEBHOOK, json={"content": f"[R11] {now():%H:%M} | {msg}"}, timeout=8)
        logging.info(f"DISCORD → {msg}")
    except Exception as e:
        logging.error(f"Discord failed: {e}")

# ==================== SAFE DATA FUNCTIONS ====================
def safe_aggs_cache = {}
def safe_aggs(t, m=1, ts="minute", lim=100):
    key = (t,m,ts,lim)
    if key in safe_aggs_cache:
        return safe_aggs_cache[key]
    try:
        r = client.get_aggs(t, m, ts, limit=lim)
        bars = list(r) if r else []
        safe_aggs_cache[key] = bars
        return bars
    except Exception as e:
        logging.warning(f"aggs fail {t} {ts}×{m}: {e}")
        return []

def get_price(t): 
    b = safe_aggs(t,1,"minute",1)
    return b[-1].close if b else None

def vwap_last20(t):
    b = safe_aggs(t,1,"minute",50)
    if len(b) < 20: return None
    vol = sum(x.volume for x in b[-20:])
    if vol == 0: return b[-1].close
    return sum((x.vwap or x.close)*x.volume for x in b[-20:]) / vol

def rsi14(t):
    b = safe_aggs(t,1,"minute",30)
    if len(b) < 15: return 50
    gains = sum(max(x.close-x.open,0) for x in b[-14:])
    losses = sum(abs(min(x.close-x.open,0)) for x in b[-14:]) or 1
    return 100 - 100/(1 + gains/losses)

def vol_mult(t):
    b = safe_aggs(t,1,"minute",50)
    if len(b) < 21: return 1.0
    return b[-1].volume / (sum(x.volume for x in b[-21:-1])/20 or 1)

def big_gap(t):
    b = safe_aggs(t,15,"minute",10)
    if len(b) < 2: return 0, False
    prev = b[-2]
    p = get_price(t)
    if p is None: return 0, False
    bonus = abs(p - (prev.high if p>prev.high else prev.low)) > (prev.high-prev.low)*0.5
    if p > prev.high: return 1, bonus
    if p < prev.low:  return -1, bonus
    return 0, False

def get_contract(ticker, side):
    spot = get_price(ticker)
    if not spot: return None,None,None
    ctype = "call" if side=="LONG" else "put"
    days = [0,1,2,3,4,5] if ticker in ["SPY","QQQ","IWM"] else [1,2,3,4,5]
    cands = []
    for d in days:
        exp = (now()+timedelta(days=d)).strftime("%Y-%m-%d")
        try:
            for c in client.list_options_contracts(ticker, contract_type=ctype, expiration_date=exp, limit=150):
                try:
                    q = client.get_option_quote(c.ticker)
                    if not q or not q.ask or not q.bid: continue
                    if not (0.22 <= q.ask <= 0.45): continue
                    if q.bid < 0.10 or getattr(q,'open_interest',0) < 300: continue
                    if abs(float(c.strike_price)-spot)/spot > 0.05: continue
                    cands.append((q.ask, q.open_interest or 0, c.ticker, f"{d}DTE"))
                except: continue
        except: continue
    if not cands: return None,None,None
    cands.sort(key=lambda x: (-x[1], x[0]))
    return cands[0][2], round(cands[0][0],2), cands[0][3]

def cream(t, side):
    score = 7.0
    vix = get_vix1d()
    if vix >= 24: score += 3
    vm = vol_mult(t)
    if vm > 4.5: score += 2
    elif vm > 3.2: score += 1.2
    r = rsi14(t)
    tgt = 32 if side=="LONG" else 68
    if abs(r-tgt) < 6: score += 1.8
    vdist = abs(get_price(t) - vwap_last20(t)) / vwap_last20(t) if vwap_last20(t) else 0
    if vdist > 0.009: score += 1.2
    if t in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI","PLTR"]: score += 1.0
    g, bonus = big_gap(t)
    if (side=="LONG" and g==1) or (side=="SHORT" and g==-1):
        if bonus: score += 3.0
    return min(score, 10.0)

def get_vix1d():
    b = safe_aggs("VIX",1,"day",3)
    return b[-1].close if b else 18.0

# ==================== SIZING ====================
BASE = 17
CAP  = 70
def size():
    global daily_pnl
    return min(BASE + max(0, daily_pnl // 650), CAP)

# ==================== MAIN LOOP ====================
send("R11 live – 8.4 cream – logging to repo root")
while True:
    try:
        for t in TICKERS:
            price = get_price(t)
            vwap = vwap_last20(t)
            if price is None or vwap is None:
                continue

            score_l = cream(t, "LONG")
            score_s = cream(t, "SHORT")
            sz = size()

            if score_l >= 8.4 and price > vwap and rsi14(t) < 36 and f"L{t}" not in alerts_today:
                c, pr, dte = get_contract(t, "LONG")
                if c:
                    alerts_today.add(f"L{t}")
                    send(f"{t} {dte} CALL {score_l:.1f} [{sz}] @ ${pr}")
                    daily_pnl += sz * 100 * 2.9
                    logging.info(f"LONG  {t:5} {c[:30]:30} ${pr:.2f} size={sz}")

            if score_s >= 8.4 and price < vwap and rsi14(t) > 64 and f"S{t}" not in alerts_today:
                c, pr, dte = get_contract(t, "SHORT")
                if c:
                    alerts_today.add(f"S{t}")
                    send(f"{t} {dte} PUT {score_s:.1f} [{sz}] @ ${pr}")
                    daily_pnl += sz * 100 * 2.7
                    logging.info(f"SHORT {t:5} {c[:30]:30} ${pr:.2f} size={sz}")

        # EOD
        if now().hour == 13 and now().minute < 5:
            send(f"EOD – {len(alerts_today)//2} trades – ~${daily_pnl:,.0f}")
            logging.info(f"EOD – trades:{len(alerts_today)//2} pnl:${daily_pnl:,.0f}")

        # Midnight reset
        if now().hour == 2 and now().minute < 5:
            alerts_today.clear()
            daily_pnl = 0
            logging.info("=== NEW DAY RESET ===")

        # clear cache every hour to stay fresh
        if now().minute == 0:
            safe_aggs_cache.clear()

        time.sleep(300)

    except Exception as e:
        logging.error(f"CRASH: {e}", exc_info=True)
        send(f"crash: {str(e)[:100]}")
        time.sleep(300)
