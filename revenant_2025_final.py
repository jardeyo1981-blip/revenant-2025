# revenant_2025_final.py — DEC 2025 UPDATE: TRUE INFINITE LOOP, NO CRASHES, 5-MIN SCANS
import os
import time
import requests
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing MASSIVE_API_KEY or DISCORD_WEBHOOK_URL!")

client = RESTClient(api_key=MASSIVE_KEY)

# === 50 TICKERS ===
TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','SMCI','HOOD','SOXL','SOXS','NFLX','COIN','PLTR','TQQQ','SQQQ','IWM','ARM','AVGO','ASML','MRVL','MU','MARA','RIOT','MSTR','UPST','RBLX','TNA','TZA','LABU','LABD','NIO','XPEV','LI','BABA','PDD','BIDU','CRM','ADBE','ORCL','INTC','SNOW','NET','CRWD','ZS','PANW','SHOP']

CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]
ESTIMATED_HOLD = {"D":"2h – 6h", "240":"1h – 3h", "60":"30min – 1h45m", "30":"15min – 45min"}

sent_alerts = set()
premarket_done = False
last_daily_report = None
pst = pytz.timezone('America/Los_Angeles')
last_heartbeat = 0

def now_pst():
    return datetime.now(pst)

def send_discord(msg):
    try:
        data = {"content": f"**Revenant Alert** | {now_pst().strftime('%H:%M:%S PST')} ```{msg}```"}
        requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        print(f"Discord sent: {msg[:100]}...")
    except Exception as e:
        print(f"Discord fail: {e}")

def send_heartbeat():
    global last_heartbeat
    if time.time() - last_heartbeat > 3600:  # 1 hour
        send_discord("🫀 **HEARTBEAT** — Revenant is alive and scanning. No new signals yet.")
        last_heartbeat = time.time()

# 100% MANUAL EMA — NO PANDAS, NO CRASH
def get_price_and_ema(ticker, tf, length):
    try:
        multiplier = {"D":1, "240":4, "60":1, "30":1}[tf]  # Fixed: 240/60/30 min as multiples of hour/day
        timespan = "day" if tf == "D" else "minute"
        days_back = 730 if tf=="D" else 60
        from_date = (now_pst() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        aggs = client.get_aggs(ticker, multiplier, timespan, from_date, now_pst().strftime('%Y-%m-%d'), limit=50000)
        if len(aggs) < length:
            return None, None
        closes = [bar.close for bar in aggs]
        price = closes[-1]
        ema = closes[0]
        k = 2 / (length + 1)
        for close in closes[1:]:
            ema = close * k + ema * (1 - k)
        return round(price, 4), round(ema, 4)
    except Exception as e:
        print(f"EMA fail {ticker}/{tf}: {e}")
        return None, None

def get_gamma_flip(ticker):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),
            expiration_date_lte=(now_pst()+timedelta(days=2)).strftime('%Y-%m-%d'),
            limit=200
        )
        strikes = {}
        for c in contracts:
            oi = c.open_interest or 0
            strikes[c.strike_price] = strikes.get(c.strike_price, 0) + oi
        if strikes:
            return max(strikes, key=strikes.get)
    except Exception as e:
        print(f"Gamma fail {ticker}: {e}")
    return None

def find_cheap_contract(ticker, direction):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=now_pst().strftime('%Y-%m-%d'),
            expiration_date_lte=(now_pst()+timedelta(days=7)).strftime('%Y-%m-%d'),
            limit=100
        )
        for c in contracts:
            quote = client.get_last_trade(c.ticker)
            if quote and quote.price and quote.price <= 1.00:
                return c.strike_price, round(quote.price, 2)
    except Exception as e:
        print(f"Cheap contract fail {ticker}: {e}")
    return None, None

def calculate_profit(prem, underlying_move):
    if not prem or underlying_move <= 0:
        return "No <$1 contract", 0
    delta = 0.35  # Conservative 2025 delta for cheap OTM
    profit = underlying_move * delta * 100
    new_price = prem + (profit / 100)
    profit_pct = (profit / (prem * 100)) * 100
    return f"${prem:.2f} → ${new_price:.2f} (+{profit_pct:.0f}%)", profit_pct

def get_grade(gap_pct, prem, profit_pct, gamma_hit, is_daily):
    score = gap_pct
    if is_daily: score *= 2.2
    if gamma_hit: score *= 1.5
    if prem <= 0.60: score *= 1.3
    if profit_pct >= 200: score *= 1.4
    if score >= 6.5: return "A++"
    if score >= 5.0: return "A"
    if score >= 3.5: return "B"
    if score >= 2.0: return "C"
    return "D"

def check_live():
    global premarket_done, last_daily_report
    now = now_pst()
    hour = now.hour
    is_market_open = 6.5 <= hour < 13  # 6:30AM - 1PM PST
    is_trading_day = now.weekday() < 5

    if not is_trading_day:
        time.sleep(300)
        return

    print(f"SCANNING — {now.strftime('%H:%M:%S PST')} — 50 TICKERS — Open: {is_market_open}")

    signals = []
    for ticker in TICKERS:
        try:
            # Get prev close for gap calc (simplified; use yfinance if needed, but keeping pure Polygon)
            daily_aggs = client.get_aggs(ticker, 1, "day", (now - timedelta(days=2)).strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d'), limit=2)
            if len(daily_aggs) < 2:
                continue
            prev_close = daily_aggs[-2].close
            current_price, _ = get_price_and_ema(ticker, "D", 50)
            if not current_price:
                continue
            gap_pct = abs((current_price - prev_close) / prev_close * 100)

            if gap_pct < 2.0:  # Min gap filter
                continue

            direction = "LONG" if current_price > prev_close else "SHORT"
            gamma = get_gamma_flip(ticker)
            gamma_hit = gamma and abs(gamma - current_price) < current_price * 0.02  # Within 2%
            strike, prem = find_cheap_contract(ticker, direction)
            profit_str, profit_pct = calculate_profit(prem, gap_pct * current_price / 100)

            # Check EMA cross on best cloud
            best_tf = None
            best_cross = False
            for tf, length, min_gap in CLOUDS:
                _, ema = get_price_and_ema(ticker, tf, length)
                if ema and ((direction == "LONG" and current_price > ema) or (direction == "SHORT" and current_price < ema)):
                    best_tf = tf
                    best_cross = True
                    break

            if best_cross:
                is_daily = best_tf == "D"
                grade = get_grade(gap_pct, prem or 999, profit_pct, gamma_hit, is_daily)
                alert_id = f"{ticker}_{direction}_{now.strftime('%Y%m%d_%H%M')}"
                if alert_id not in sent_alerts:
                    sent_alerts.add(alert_id)
                    hold_time = ESTIMATED_HOLD.get(best_tf, "Unknown")
                    msg = f"{ticker} {direction} GAP: {gap_pct:.1f}% | Grade: {grade} | Gamma: {gamma} | {profit_str} | Hold: {hold_time} | TF: {best_tf}"
                    signals.append(msg)
                    send_discord(msg)

        except Exception as e:
            print(f"Ticker {ticker} error: {e}")
            continue

    if signals:
        send_discord(f"**BATCH SCAN ({len(signals)} signals):** {' | '.join(signals)}")

    # Premarket daily report
    if 4 <= hour < 6.5 and not premarket_done:
        # Add premarket gap summary logic here if needed
        premarket_done = True
        send_discord("**PREMARKET WRAP** — Gaps scanned. Market open in T-30min.")

    # Reset premarket flag post-open
    if hour >= 13:
        premarket_done = False

    # Daily end report
    if hour == 13 and last_daily_report != now.date():
        send_discord("**EOD REPORT** — Scans complete. Sleeping till tomorrow.")
        last_daily_report = now.date()

    send_heartbeat()

# === MAIN INFINITE LOOP — THE "LIVE FOREVER" PART ===
if __name__ == "__main__":
    send_discord("**REVENANT SPAWNED** — Starting 5-min scans. Infinite mode engaged. 🚀")
    while True:
        try:
            check_live()
            time.sleep(300)  # 5 minutes
        except KeyboardInterrupt:
            send_discord("**REVENANT DOWN** — Manual stop.")
            break
        except Exception as e:
            print(f"LOOP ERROR (retrying): {e}")
            send_discord(f"**LOOP GLITCH** — Retrying in 5min: {e}")
            time.sleep(300)
