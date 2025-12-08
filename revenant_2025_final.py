# revenant_2025_FINAL_WORKING.py
# LIVE — MASSIVE.COM + GREEN/RED + PROFIT % + A++ GRADING + DAILY POST-MORTEM
import os
import time
import requests
import yfinance as yf
import pandas as pd
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
daily_trades = []
premarket_done = False
last_daily_report = None
pst = pytz.timezone('America/Los_Angeles')

def now_pst():
    return datetime.now(pst)

def get_ema(ticker, tf, length):
    try:
        period = "60d" if tf != "D" else "2y"
        interval = "1h" if tf != "D" else "1d"
        df = yf.download(ticker, period=period, interval=interval, progress=False, threads=False)
        if df.empty or len(df) < length:
            return None
        ema_series = df['Close'].ewm(span=length, adjust=False).mean()
        last_ema = ema_series.iloc[-1]
        if pd.isna(last_ema):
            return None
        return round(last_ema, 4)
    except Exception as e:
        print(f"EMA error {ticker}: {e}")
        return None

def get_gamma_flip(ticker):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            expiration_date_gte=datetime.now().strftime('%Y-%m-%d'),
            expiration_date_lte=(datetime.now()+timedelta(days=2)).strftime('%Y-%m-%d'),
            limit=200
        )
        strikes = {}
        for c in contracts:
            oi = c.open_interest or 0
            strikes[c.strike_price] = strikes.get(c.strike_price, 0) + oi
        if strikes:
            return max(strikes, key=strikes.get)
    except:
        pass
    return None

def find_cheap_contract(ticker, direction):
    try:
        contracts = client.list_options_contracts(
            underlying_ticker=ticker,
            contract_type="call" if direction=="LONG" else "put",
            expiration_date_gte=datetime.now().strftime('%Y-%m-%d'),
            expiration_date_lte=(datetime.now()+timedelta(days=7)).strftime('%Y-%m-%d'),
            limit=100
        )
        for c in contracts:
            quote = client.get_last_trade(c.ticker)
            if quote and quote.price and quote.price <= 1.00:
                return c.strike_price, round(quote.price, 2)
    except:
        pass
    return None, None

def calculate_profit(prem, underlying_move):
    if not prem or underlying_move <= 0:
        return "No <$1 contract", 0
    delta = 0.35
    profit = underlying_move * delta * 100
    new_price = prem + (profit / 100)
    profit_pct = (profit / (prem * 100)) * 100
    return f"${prem:.2f} → ${new_price:.2f} (+{profit_pct:.0f}%)", profit_pct

def get_grade(gap_pct, prem, profit_pct, gamma_hit, is_daily):
    score = gap_pct
    if is_daily: score *= 2.2
    if gamma_hit: score *= 1.5
    if prem <= 0.60: score *= 1.5
    elif prem <= 0.80: score *= 1.3
    elif prem <= 1.00: score *= 1.1

    # VALUE SCORE
    if prem and profit_pct > 0:
        value_ratio = (prem * 100) / profit_pct
        if value_ratio <= 15: score *= 2.0
        elif value_ratio <= 25: score *= 1.7
        elif value_ratio <= 40: score *= 1.4

    if score >= 10.0 and value_ratio <= 15:
        return "A++", "Gorilla"
    elif score >= 8.0:
        return "A+", "Skull"
    elif score >= 5.5:
        return "A", "Fire"
    elif score >= 3.5:
        return "B+", "Lightning"
    elif score >= 2.0:
        return "B", "Check"
    else:
        return "C", "Warning"

def premarket_top5():
    global premarket_done
    if premarket_done: return
    plays = []
    for t in TICKERS:
        try:
            price = yf.Ticker(t).history(period="1d", interval="5m", prepost=True)['Close'].iloc[-1]
            for tf, length, min_gap in CLOUDS:
                ema = get_ema(t, tf, length)
                if ema and abs(price-ema)/price*100 >= min_gap:
                    plays.append({'ticker':t,'price':round(price,2),'target':round(ema,2),
                                  'gap':round(abs(price-ema)/price*100,2),'tf':"DAILY" if tf=="D" else tf})
        except: continue
    plays = sorted(plays, key=lambda x: x['gap'], reverse=True)[:5]
    if plays:
        msg = "**6:20 AM PST — PRE-MARKET TOP 5**\n\n"
        for i,p in enumerate(plays,1):
            msg += f"{i}. **{p['ticker']}** → {p['tf']} `{p['target']}` (**{p['gap']}%**)\n"
        send(msg)
        premarket_done = True

def check_live():
    cache = {}
    for t in TICKERS:
        try:
            df = yf.download(t, period="2d", interval="5m", progress=False, threads=False)
            if len(df) >= 3: cache[t] = df
        except: pass

    for ticker, df in cache.items():
        price = df['Close'].iloc[-1]
        prev = df.iloc[-2]
        gamma = get_gamma_flip(ticker)
        gamma_text = f"Gamma Flip ${gamma}" if gamma else "No confluence"

        for tf, length, min_gap in CLOUDS:
            ema = get_ema(ticker, tf, length)
            if ema is None:
                continue

            gap_pct = abs(price - ema) / price * 100
            aid = f"{ticker}_{tf}_{now_pst().date()}"

            direction = "LONG" if price < ema else "SHORT"
            move = abs(ema - price)
            strike, prem = find_cheap_contract(ticker, direction)
            opt = f"{strike} @ ${prem}" if prem else "No <$1 contract"
            profit_line, profit_pct = calculate_profit(prem, move)

            grade, emoji = get_grade(gap_pct, prem, profit_pct, gamma is not None, tf == "D")

            if (prev['Low'] <= ema*(1-min_gap/100) and prev['Close'] < ema and
                price >= ema and aid not in sent_alerts):
                sent_alerts.add(aid)
                send(f"{emoji} **{grade} {direction} {ticker}** ({'DAILY' if tf=='D' else tf})\n\n"
                     f"**Entry → Target**\n"
                     f"`{price:.2f}` → `{ema:.2f}` ({'+' if direction=='LONG' else '-'}{gap_pct:.2f}%)\n\n"
                     f"**Gamma Flip**\n{gamma_text}\n\n"
                     f"**Option**\n{opt}\n\n"
                     f"**Profit if target hit**\n{profit_line}\n\n"
                     f"**Hold**\n{ESTIMATED_HOLD[tf]}\n"
                     f"{now_pst().strftime('%H:%M:%S PST')}")

            elif (prev['High'] >= ema*(1+min_gap/100) and prev['Close'] > ema and
                  price <= ema and aid not in sent_alerts):
                sent_alerts.add(aid)
                send(f"{emoji} **{grade} {direction} {ticker}** ({'DAILY' if tf=='D' else tf})\n\n"
                     f"**Entry → Target**\n"
                     f"`{price:.2f}` → `{ema:.2f}` (-{gap_pct:.2f}%)\n\n"
                     f"**Gamma Flip**\n{gamma_text}\n\n"
                     f"**Option**\n{opt}\n\n"
                     f"**Profit if target hit**\n{profit_line}\n\n"
                     f"**Hold**\n{ESTIMATED_HOLD[tf]}\n"
                     f"{now_pst().strftime('%H:%M:%S PST')}")

def send(text):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text})
        print(f"{now_pst().strftime('%H:%M PST')} → Alert sent")
    except: print("Discord failed")

print("Revenant 2025 — LIVE FOREVER")
while True:
    now = now_pst()
    if now.hour == 13 and now.minute == 0 and now.weekday() < 5:
        daily_postmortem()
    if now.hour == 6 and now.minute == 20 and now.weekday() < 5:
        premarket_top5()
    if now.hour == 0 and now.minute < 5:
        premarket_done = False
        sent_alerts.clear()
    check_live()
    time.sleep(300)

send("REVENANT 2025 — BOT IS ALIVE — TEST MESSAGE — " + now_pst().strftime('%H:%M:%S PST'))
