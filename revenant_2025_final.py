# revenant_2025_FINAL_VALUE_SCORE.py
# LIVE — VALUE SCORE = % OF TARGET YOU'RE PAYING FOR (exact like you want)
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
    raise Exception("Missing secrets!")

client = RESTClient(api_key=MASSIVE_KEY)

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
        if len(df) < length: return None
        return round(df['Close'].ewm(span=length, adjust=False).mean().iloc[-1], 4)
    except: return None

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
        if strikes: return max(strikes, key=strikes.get)
    except: pass
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
    except: pass
    return None, None

def calculate_profit_and_value(prem, underlying_move):
    if not prem or underlying_move <= 0:
        return "No <$1 contract", 0, 0
    delta = 0.35
    profit_dollar = underlying_move * delta * 100
    new_price = prem + (profit_dollar / 100)
    profit_pct = (profit_dollar / (prem * 100)) * 100
    value_score = (prem * 100) / profit_dollar * 100  # % of target you're paying for
    return f"${prem:.2f} → ${new_price:.2f} (+{profit_pct:.0f}%)", profit_pct, value_score

def get_grade(gap_pct, prem, value_score, gamma_hit, is_daily):
    score = gap_pct
    if is_daily: score *= 2.2
    if gamma_hit: score *= 1.5
    if prem <= 0.60: score *= 1.5
    elif prem <= 0.80: score *= 1.3
    elif prem <= 1.00: score *= 1.1

    # VALUE SCORE BONUS
    if value_score <= 15: score *= 2.0
    elif value_score <= 25: score *= 1.7
    elif value_score <= 40: score *= 1.4

    if score >= 10.0 and value_score <= 15:
        return "A++", "🦍"
    elif score >= 8.0:
        return "A+", "💀"
    elif score >= 5.5:
        return "A", "🔥"
    elif score >= 3.5:
        return "B+", "⚡"
    elif score >= 2.0:
        return "B", "✅"
    else:
        return "C", "⚠️"

def check_live():
    cache = {}
    for t in TICKERS:
        try:
            df = yf.download(t, period="2d", interval="5m", progress=False, threads=False)
            if len(df)>=3: cache[t] = df
        except: pass

    for ticker, df in cache.items():
        price = df['Close'].iloc[-1]
        prev = df.iloc[-2]
        gamma = get_gamma_flip(ticker)
        gamma_text = f"Gamma Flip ${gamma}" if gamma else "No confluence"

        for tf, length, min_gap in CLOUDS:
            ema = get_ema(ticker, tf, length)
            if ema is None or (isinstance(ema, float) and str(ema) == 'nan'):
                continue

            gap_pct = abs(price-ema)/price*100
            aid = f"{ticker}_{tf}_{now_pst().date()}"

            direction = "LONG" if price < ema else "SHORT"
            move = abs(ema - price)
            strike, prem = find_cheap_contract(ticker, direction)
            opt = f"{strike} @ ${prem}" if prem else "No <$1 contract"
            profit_line, profit_pct, value_score = calculate_profit_and_value(prem, move)

            grade, emoji = get_grade(gap_pct, prem, value_score, gamma is not None, tf == "D")

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
                     f"`{price:.2f}` → `{ema:.2f}` ({'+' if direction=='LONG' else '-'}{gap_pct:.2f}%)\n\n"
                     f"**Gamma Flip**\n{gamma_text}\n\n"
                     f"**Option**\n{opt}\n\n"
                     f"**Profit if target hit**\n{profit_line}\n\n"
                     f"**Hold**\n{ESTIMATED_HOLD[tf]}\n"
                     f"{now_pst().strftime('%H:%M:%S PST')}")

# [rest of your functions unchanged]

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
