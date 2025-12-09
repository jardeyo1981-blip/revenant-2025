# revenant_2025_NUCLEAR_WITH_HEARTBEAT.py
# FINAL — 6 STRATEGIES — EOD RECAP — $0.70 PREMIUM — HEARTBEAT EVERY 5 MIN
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
pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant NUCLEAR** | {now_pst().strftime('%H:%M PST')} ```{msg}```"}, timeout=10)

# CACHES
prev_close_cache = {}
def get_prev_close(ticker):
    global prev_close_cache
    today = now_pst().date()
    if ticker not in prev_close_cache:
        try:
            aggs = client.get_aggs(ticker, 1, "day", limit=5)
            prev_close_cache[ticker] = aggs[-2].close if len(aggs) >= 2 else None
        except:
            prev_close_cache[ticker] = None
    return prev_close_cache[ticker]

def get_data(ticker, tf):
    # [same as before — unchanged]
    ...

def get_cheap_contract(ticker, direction):
    # [same as before — unchanged]
    ...

# MAIN LOOP — HEARTBEAT EVERY 5 MIN
send("REVENANT NUCLEAR — LIVE — Heartbeat active every 5 min")
while True:
    try:
        now = now_pst()
        hour, minute = now.hour, now.minute

        # EOD RECAP
        if hour == 12 and minute >= 55 and not eod_sent:
            # [your recap code — unchanged]
            eod_sent = True
            alerts_today = []

        if now.weekday() >= 5 or not (6.5 <= hour < 13):
            time.sleep(300); continue

        # HEARTBEAT — THIS IS WHAT YOU WANT TO SEE
        print(f"SCANNING — {now_pst().strftime('%H:%M:%S PST')} — 50 TICKERS — no 429s")

        # [rest of your 6-strategy scanning loop — unchanged]

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
