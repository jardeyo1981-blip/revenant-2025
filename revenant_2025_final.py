import os, time, requests, pytz
from datetime import datetime, timedelta
from polygon import RESTClient

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK: exit("Set DISCORD_WEBHOOK_URL!")

INDEX = ["SPY","QQQ","IWM","XLF","XLK","XLE","XLV","XBI"]
STOCKS = ["NVDA","TSLA","META","AAPL","AMD","SMCI","MSTR","COIN","AVGO","NFLX",
          "AMZN","GOOGL","MSFT","ARM","SOXL","TQQQ","SQQQ","UVXY","ARKK","HOOD",
          "PLTR","RBLX","SNOW","CRWD","SHOP"]
TICKERS = INDEX + STOCKS

alerts_today = set()
earnings_today = set()
last_heartbeat = 0
eod_sent = False
pst = pytz.timezone('America/Los_Angeles')
def now(): return datetime.now(pst)

def send(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": f"**REVENANT LOCKED FOREVER** | {now().strftime('%H:%M PST')}\n```{msg}```"})
    except Exception as e:
        print(f"Error sending Discord message: {e}")

try:
    client = RESTClient(api_key=os.getenv("MASSIVE_API_KEY"))
except Exception as e:
    print(f"Error initializing Polygon client: {e}")
    exit("Failed to initialize Polygon client")

# VIX1D with Dynamic Threshold
def get_vix1d():
    try:
        bars = safe_aggs("VIX1D", limit=2)
        return bars[-1].close if bars else 18.0
    except Exception as e:
        print(f"Error getting VIX1D: {e}")
        return 18.0

def dynamic_vix_threshold():
    vix = get_vix1d()
    if vix > 30:
        return 28
    elif vix > 22:
        return 24
    else:
        return 20

# EARNINGS OVERRIDE with Expanded Pool Activation
def load_earnings_today():
    global earnings_today
    try:
        today = now().strftime('%Y-%m-%d')
        earnings = client.list_earnings(date=today, limit=200)
        earnings_today = {e.ticker for e in earnings if e.ticker in TICKERS}
        # Expanded pool activation logic
        if len(earnings_today) > 10:  # Example threshold for pool expansion
            send(f"Earnings pool expanded due to {len(earnings_today)} tickers with earnings today.")
    except Exception as e:
        print(f"Error loading earnings: {e}")
        earnings_today = set()

# Hybrid DTE
def get_expiration_days(ticker):
    if ticker in earnings_today: return [3,4,5]
    weekday = now().weekday()
    if ticker in INDEX: return [0] if weekday <= 1 else []
    if weekday <= 1: return [4,5]
    elif weekday <= 3: return [1,2,3]
    else: return [1,2,3,4,5]

# Dynamic Premium Cap
def get_contract(ticker, direction):
    days = get_expiration_days(ticker)
    if not days: return None, None, None
    ctype = "call" if "LONG" in direction else "put"
    spot = safe_aggs(ticker, limit=1)[-1].close
    candidates = []
    for d in days:
        exp = (now() + timedelta(days=d)).strftime('%Y-%m-%d')
        try:
            contracts = client.list_options_contracts(underlying_ticker=ticker, contract_type=ctype,
                                                      expiration_date=exp, limit=200)
            for c in contracts:
                try:
                    q = client.get_option_quote(c.ticker)
                    if not q or q.ask is None or q.ask > dynamic_premium_cap(q.ask, spot) or q.bid < 0.10: continue
                    strike = float(c.ticker.split(ctype.upper())[-1])
                    if abs(strike - spot) / spot <= 0.048:
                        if (q.ask - q.bid) / q.ask <= 0.35 and getattr(q, 'open_interest', 0) > 300:
                            candidates.append((q.ask, q.open_interest, c.ticker, f"{d}DTE"))
                except Exception as e:
                    print(f"Error processing contract for {ticker}: {e}")
                    continue
        except Exception as e:
            print(f"Error getting contracts for {ticker} on {exp}: {e}")
            continue
    if candidates:
        candidates.sort(key=lambda x: (-x[1], x[0]))
        best = candidates[0]
        return best[2], round(best[0], 2), best[3]
    return None, None, None

def dynamic_premium_cap(ask_price, spot_price):
    # Dynamic cap based on volatility and spot price
    vix = get_vix1d()
    volatility_factor = 0.02 if vix > 25 else 0.015
    return min(0.30, spot_price * volatility_factor)

# Adjusted Earnings Threshold Request
def check_earnings_reminder():
    now_time = now()
    if now_time.weekday() == 4 and now_time.hour == 12 and now_time.minute == 55:  # Friday at 12:55 PST
        send("Reminder: Update earnings pool data before Monday during earnings season.")

# MTF Air-Gap
def mtf_air_gap(ticker):
    try:
        bars15 = safe_aggs(ticker, 15, "minute", limit=10)
        if len(bars15) < 2: return 0, False
        prev = bars15[-2]; curr = bars15[-1]
        price = safe_aggs(ticker, limit=1)[-1].close
        air_gap = 0
        if price > prev.high and curr.low > prev.high: air_gap = 1
        elif price < prev.low and curr.high < prev.low: air_gap = -1
        # Air gap bonus impact
        bonus = abs(price - (prev.high if air_gap > 0 else prev.low)) > (prev.high - prev.low) * 0.5
        return air_gap, bonus
    except Exception as e:
        print(f"Error calculating MTF air-gap for {ticker}: {e}")
        return 0, False

# Cloud-First Target
def get_target(ticker, direction, entry_price):
    for tf, limit in [("D", 200), ("240", 100), ("60", 80)]:
        try:
            bars = safe_aggs(ticker, timeframe=tf, limit=limit)
            if len(bars) < 50: continue
            ema34 = sum(b.close for b in bars[-34:]) / 34
            ema50 = sum(b.close for b in bars[-50:]) / 50
            upper = max(ema34, ema50)
            lower = min(ema34, ema50)
            if "LONG" in direction and upper > entry_price: return round(upper, 2)
            if "SHORT" in direction and lower < entry_price: return round(lower, 2)
        except Exception as e:
            print(f"Error getting target for {ticker} with timeframe {tf}: {e}")
            continue
    try:
        daily = safe_aggs(ticker, 1, "day", limit=20)
        atr = sum(b.high - b.low for b in daily[-14:]) / 14
    except Exception as e:
        print(f"Error calculating ATR for {ticker}: {e}")
        atr = entry_price * 0.015
    return round(entry_price + (atr if "LONG" in direction else -atr), 2)

# Post Earnings Short Strategy
def post_earnings_short_strategy(ticker):
    if ticker in earnings_today:
        try:
            bars = safe_aggs(ticker, 1, "day", limit=5)
            if len(bars) < 2: return None
            post_earnings_price = bars[-1].close
            pre_earnings_price = bars[-2].close
            if post_earnings_price < pre_earnings_price * 0.95:  # 5% drop post-earnings
                return "SHORT"
        except Exception as e:
            print(f"Error calculating post-earnings short for {ticker}: {e}")
    return None

# No Picking Alerts
def no_picking_alerts(ticker, direction, price, target, contract, premium, dte, score):
    try:
        bars = safe_aggs(ticker, 1, "day", limit=5)
        if len(bars) < 2: return False
        recent_high = max(b.high for b in bars[-5:])
        recent_low = min(b.low for b in bars[-5:])
        if "LONG" in direction and price > recent_high * 0.98:  # Within 2% of recent high
            return True
        if "SHORT" in direction and price < recent_low * 1.02:  # Within 2% of recent low
            return True
        return False
    except Exception as e:
        print(f"Error calculating no-picking alert for {ticker}: {e}")
        return False

# CREAM SCORE with Synergistic Effect
def cream_score(ticker, direction, vol_mult, rsi, vwap_dist, air_gap_bonus=False):
    score = 7.0
    if get_vix1d() >= dynamic_vix_threshold(): score += 3
    if vol_mult > 4.5: score += 2
    elif vol_mult > 3.2: score += 1.2
    if abs(rsi - (32 if "LONG" in direction else 68)) < 6: score += 1.8
    if vwap_dist > 0.009: score += 1.2
    if ticker in ["NVDA","TSLA","SOXL","MSTR","COIN","AMD","SMCI","PLTR"]: score += 1.0
    if air_gap_bonus: score += 3.0
    # Synergistic effect with post-earnings short
    if post_earnings_short_strategy(ticker) == "SHORT" and direction == "SHORT":
        score += 2.0
    if ticker in earnings_today: score = 10.0
    return min(score, 10)

# SAFE AGGS
def safe_aggs(ticker, multiplier=1, timespan="minute", limit=100, timeframe=None):
    try:
        return client.get_aggs(ticker, multiplier, timespan, limit=limit) or []
    except Exception as e:
        print(f"Error getting aggs for {ticker}: {e}")
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}"
            params = {"limit": limit}
            response = requests.get(url, params=params, headers={"Authorization": f"Bearer {os.getenv('MASSIVE_API_KEY')}"})
            return response.json().get('results', []) if response.status_code == 200 else []
        except Exception as e:
            print(f"Backup aggs error for {ticker}: {e}")
            return []

# RSI Calculation
def calculate_rsi(bars):
    if len(bars) < 14: return 50.0
    gains = []; losses = []
    for i in range(1, 14):
        change = bars[i].close - bars[i-1].close
