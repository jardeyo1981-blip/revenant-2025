# revenant_2025_2_to_3_alerts_per_day_SIMPLE_TOGGLE.py
# FINAL — ZERO 429s + LOW-LIQ ALIVE + SIMPLE FILE-BASED TEST TOGGLE
import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

def check_live():
    mode = get_test_mode()

    # Send forced test alerts every scan
    send_forced_test_alerts()

    # FULL BYPASS for forced mode — loop forever 24/7
    if mode == 'forced':
        print(f"FORCED MODE ACTIVE — SCANNING 24/7 — {now_pst().strftime('%H:%M:%S PST')}")
        # No guard — continue to scan/print (you can add fake scan logs here if wanted)
    else:
        # Normal guard for live/normal mode
        if now_pst().weekday() >= 5 or not (6.5 <= now_pst().hour < 13):
            time.sleep(300)
            return

    # ... rest of real scan code (ATR cache, ticker loop, etc.)
# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing keys!")
client = RESTClient(api_key=MASSIVE_KEY)

# === TICKERS & SETTINGS (unchanged) ===
TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50), ("240",50), ("60",50), ("30",50), ("15",50)]
ESTIMATED_HOLD = {"D":"2h–6h", "240":"1h–3h", "60":"30m–1h45m", "30":"15m–45m", "15":"10m–30m"}

MIN_GAP = 1.4
MAX_PREMIUM = 1.50
GAMMA_TOLERANCE = 0.04

sent_alerts = set()
last_heartbeat = 0
pst = pytz.timezone('America/Los_Angeles')

# === SIMPLE RUNTIME TOGGLE ===
def get_test_mode():
    try:
        with open('test_mode.txt', 'r') as f:
            mode = f.read().strip().lower()
        if mode == 'forced':
            return 'forced'
        elif mode == 'normal':
            return 'normal'
        else:
            return 'off'
    except:
        return 'off'  # default to live if file missing

# === DISCORD (prefix based on current mode) ===
def send_discord(msg):
    mode = get_test_mode()
    prefix = ""
    if mode == 'forced':
        prefix = "**FORCED TEST** — "
    elif mode == 'normal':
        prefix = "**TEST MODE** — "
    full_msg = f"{prefix}**Revenant 2.0** | {datetime.now(pst).strftime('%H:%M:%S PST')} ```{msg}```"
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": full_msg}, timeout=10)
        print(f"ALERT → {full_msg}")
    except: pass

# === FORCED TEST ALERTS ===
def send_forced_test_alerts():
    if get_test_mode() != 'forced':
        return
    fake_alerts = [
        "NVDA LONG | 3.2% | A++ | Gamma | 148c@$1.05 | 2h–6h | D",
        "TSLA SHORT | 2.8% | A+ | VolExp | 440p@$0.95 | 1h–3h | 240",
        "SMCI LONG | 5.1% | A++ | Gamma | 58c@$1.20 | 30m–1h45m | 60",
        "COIN SHORT | 4.3% | A | EMA | 365p@$0.78 | 15m–45m | 30",
        "MARA SHORT | 9.7% | A++ | VolExp | 18p@$0.65 | 10m–30m | 15",
        "NIO LONG | 6.5% | A+ | Gamma | 8c@$0.88 | 30m–1h45m | 60",
        "BABA SHORT | 3.9% | B | EMA | 112p@$1.10 | 2h–6h | D"
    ]
    for fake in fake_alerts:
        send_discord(fake)
        time.sleep(1)

# === REST OF THE SCRIPT (caches, helpers, scan — unchanged) ===
# ... (paste all the previous functions: get_prev_close, get_current_atr_and_range, 
# get_price_and_ema, get_gamma_flip, find_cheap_contract, get_grade, etc.)

# In check_live(), replace the old send_forced_test_alerts() call with:
    send_forced_test_alerts()

# Startup message:
mode = get_test_mode()
mode_text = {"forced": "FORCED TEST ACTIVE", "normal": "NORMAL TEST MODE", "off": "LIVE"}.get(mode, "LIVE")
send_discord(f"REVENANT 2.0 — {mode_text} — Deployed & hunting")
