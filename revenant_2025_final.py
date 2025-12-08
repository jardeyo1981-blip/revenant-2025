# revenant_2025_green_baby.py
# THE VERSION THAT WENT GREEN — NO POST-MORTEM, NO GRADING, JUST PURE LIVE ALERTS
import os
import time
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pytz
from polygon import RESTClient

# === SECRETS ===
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

if not MASSIVE_KEY or not DISCORD_WEBHOOK:
    raise Exception("Missing MASSIVE_API_KEY or DISCORD_WEBHOOK_URL!")

client = RESTClient(api_key=MASSIVE_KEY)

TICKERS = ['SPY','QQQ','IWM','NVDA','TSLA','AAPL','META','AMD','AMZN','GOOGL','MSFT','SMCI']
CLOUDS = [("D",50,2.8), ("240",50,2.2), ("60",50,1.8), ("30",50,1.5)]

sent_alerts = set()
premarket_done = False
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
            if len(df)>=3: cache[t] = df
        except: pass

    for ticker, df in cache.items():
        price = df['Close'].iloc[-1]
        prev = df.iloc[-2]
        gamma = get_gamma_flip(ticker)
        gamma_text = f"Gamma Flip ${gamma}" if gamma else "No confluence"

        for tf, length, min_gap in CLOUDS:
            ema = get_ema(ticker, tf, length)
            if ema is None: continue
            gap_pct = abs(price-ema)/price*100
            aid = f"{ticker}_{tf}_{now_pst().date()}"

            if (prev['Low'] <= ema*(1-min_gap/100) and prev['Close'] < ema and
                price >= ema and aid not in sent_alerts):
                sent_alerts.add(aid)
                strike, prem = find_cheap_contract(ticker, "LONG")
                opt = f"{strike} @ ${prem}" if prem else "No <$1 call"
                send(f"{'DAILY' if tf=='D' else tf} LONG {ticker}\n\n"
                     f"**Entry → Target**\n"
                     f"`{price:.2f}` → `{ema:.2f}` (+{gap_pct:.2f}%)\n\n"
                     f"**Gamma Flip**\n{gamma_text}\n\n"
                     f"**Option**\n{opt}\n\n"
                     f"{now_pst().strftime('%H:%M:%S PST')}")

            elif (prev['High'] >= ema*(1+min_gap/100) and prev['Close'] > ema and
                  price <= ema and aid not in sent_alerts):
                sent_alerts.add(aid)
                strike, prem = find_cheap_contract(ticker, "SHORT")
                opt = f"{strike} @ ${prem}" if prem else "No <$1 put"
                send(f"{'DAILY' if tf=='D' else tf} SHORT {ticker}\n\n"
                     f"**Entry → Target**\n"
                     f"`{price:.2f}` → `{ema:.2f}` (-{gap_pct:.2f}%)\n\n"
                     f"**Gamma Flip**\n{gamma_text}\n\n"
                     f"**Option**\n{opt}\n\n"
                     f"{now_pst().strftime('%H:%M:%S PST')}")

def send(text):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": text})
        print(f"{now_pst().strftime('%H:%M PST')} → Alert sent")
    except: print("Discord failed")

print("Revenant 2025 — LIVE FOREVER")
while True:
    now = now_pst()
    if now.hour == 6 and now.minute == 20 and now.weekday() < 5:
        premarket_top5()
    if now.hour == 0 and now.minute < 5:
        premarket_done = False
        sent_alerts.clear()
    check_live()
    time.sleep(300)
