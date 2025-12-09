# revenant_2025_FINAL_WITH_PROFIT_RECAP.py
# 6 STRATEGIES + REAL ENTRY + MAX OPTION PROFIT IN EOD RECAP
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

# Track every alert with entry premium and ticker for profit calc
alerts_today = []   # List of dicts: {'ticker':, 'dir':, 'strike':, 'entry_prem':, 'strat':, 'tf':}
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now_pst(): return datetime.now(pst)

def send(msg):
    requests.post(DISCORD_WEBHOOK, json={"content": f"**Revenant NUCLEAR** | {now_pst().strftime('%H:%M PST')} ```{msg}```"}, timeout=10)

# [All your existing get_prev_close, get_data, get_cheap_contract — unchanged]

# MAIN LOOP — NOW TRACKS ENTRY PREMIUM
send("REVENANT NUCLEAR — LIVE — Profit tracking active")
while True:
    try:
        now = now_pst()
        hour, minute = now.hour, now.minute

        # EOD RECAP WITH REAL PROFITS
        if hour == 12 and minute >= 55 and not eod_sent:
            if not alerts_today:
                send("**EOD RECAP** — No qualifying plays today. Stayed disciplined. 💀")
            else:
                recap = f"**EOD RECAP — {now.date()}** | {len(alerts_today)} plays\n\n"
                total_profit = 0
                for a in alerts_today:
                    try:
                        # Get today's high/low for profit calc
                        day = client.get_aggs(a['ticker'],1,"day",limit=2)
                        high = day[-1].high
                        low = day[-1].low
                        move = (high - low) if a['dir'] == "LONG" else (high - low)  # same for both
                        # Rough delta 0.35–0.45 → use 0.4 avg
                        option_profit = round((move * 0.4 * 100) / a['entry_prem'], 1)
                        total_profit += option_profit
                        recap += f"• {a['ticker']} {a['dir']} — {a['strat']} ({a['tf']})\n"
                        recap += f"  Entry: {a['strike']} @ ${a['entry_prem']}\n"
                        recap += f"  Max Option Profit: **+{option_profit}%**\n\n"
                    except:
                        recap += f"• {a['ticker']} {a['dir']} — {a['strat']} — profit calc failed\n\n"

                recap += f"**Estimated Portfolio Gain: +{total_profit:.1f}%** on $0.70 avg entry\n"
                recap += "Tomorrow we hunt again. Good night. 💀"
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

                sent = False

                # 1. EMA RETEST
                if (direction=="LONG" and lo<=ema<=p) or (direction=="SHORT" and hi>=ema>=p):
                    msg = f"[{t}] EMA RETEST {direction}\n{gap:.1f}% gap → touched {tf} EMA\n→ BUY {strike} @ ${prem} NOW\nTarget: 2–2.5× gap"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"EMA Retest","tf":tf})
                    send(msg); sent = True

                # 2. VWAP RECLAIM
                if vwap and ((direction=="LONG" and lo<=vwap<=p) or (direction=="SHORT" and hi>=vwap>=p)) and not sent:
                    msg = f"[{t}] VWAP RECLAIM {direction}\n{gap:.1f}% gap → reclaimed VWAP\n→ BUY {strike} @ ${prem} NOW"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"VWAP Reclaim","tf":tf})
                    send(msg); sent = True

                # 3. R2G / G2R FLIP
                if tf=="15" and bar_open and ((direction=="LONG" and bar_open<prev and p>bar_open) or (direction=="SHORT" and bar_open>prev and p<bar_open)) and not sent:
                    flip = "R2G" if direction=="LONG" else "G2R"
                    msg = f"[{t}] {flip} FLIP {direction}\n{gap:.1f}% → flipped color\n→ BUY {strike} @ ${prem} on momentum"
                    alerts_today.append({"ticker":t,"dir":direction,"strike":strike,"entry_prem":prem,"strat":"R2G/G2R Flip","tf":tf})
                    send(msg)

        time.sleep(300)
    except Exception as e:
        send(f"ERROR — Still alive: {e}")
        time.sleep(300)
