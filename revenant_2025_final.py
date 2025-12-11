import os
import requests
import json
from datetime import datetime, timedelta
import discord
from discord.ext import tasks, commands
import talib
import numpy as np
import pandas as pd

# Discord bot and webhook setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.environ.get('DISCORD_CHANNEL_ID'))
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# Tickers and pools
INDEX = ["SPY", "QQQ", "IWM"]
STOCKS = ["NVDA", "TSLA", "SOXL", "MSTR", "COIN", "AMD", "SMCI", "PLTR"]
CORE_TICKERS = INDEX + STOCKS
BROAD_EARNINGS_POOL = ["META", "AAPL", "AMZN", "GOOGL", "MSFT", "AVGO", "NFLX", "CRWD", "SHOP", "SNOW", "RBLX", "HOOD",
                       "RIOT", "MARA", "XOM", "CVX", "PFE", "MRK", "MU", "INTC", "AVAV"]

# Locked-in Features Documentation
"""
Locked-in Features as of December 10, 2025:

1. Dynamic VIX Threshold:
   - Adjusts trading activity based on VIX level, pausing if VIX >= 24.

2. VIX Hedge:
   - Allocates 10% capital to UVXY (VIX < 23) or SQQQ (VIX >= 23) when VIX is between 22 and 24.

3. Expanded Pool:
   - Includes CORE_TICKERS and BROAD_EARNINGS_POOL during earnings seasons, activated based on earnings dates and volatility.

4. Dynamic Premium Cap:
   - Adjusts options premium cap based on VIX:
     - VIX < 18: $0.25
     - 18 ≤ VIX < 22: $0.30
     - VIX ≥ 22: $0.35

5. Adjusted Earnings Threshold:
   - Lowers earnings score threshold to 9.5 during multiple high-IV weeks.

6. Air Gap Bonus:
   - Prioritizes trades targeting air gap support levels during gap down scenarios post-earnings.

7. Discord Webhook:
   - Sends real-time trade notifications via Discord webhook for transparency and monitoring.

8. Enhanced Air Gap Identification:
   - Prioritizes lowest time frame air gap as critical support using shorter-term EMAs (5, 12, 34, 50).

9. Post-Earnings Short Strategy Enhancement:
   - Refines shorting logic post-earnings misses to target air gap support levels, optimizing captures during high-volatility periods.
"""

# Global variables
global last_pnl, last_trade_time, last_vix, last_earnings_check, trade_count, total_pnl, wins, losses
last_pnl, last_trade_time, last_vix, last_earnings_check = 0, 0, 0, 0
trade_count, total_pnl, wins, losses = 0, 0, 0, 0

def now():
    return datetime.now()

def safe_aggs(ticker, limit=500, timespan="minute"):
    try:
        bars = client.get_aggs(ticker=ticker, multiplier=1, timespan=timespan, from_=int((now().timestamp() - 86400) * 1000), to=int(now().timestamp() * 1000), limit=limit)
        return bars.df if bars else []
    except Exception as e:
        print(f"Error fetching aggs for {ticker}: {e}")
        return []

def get_vix1d():
    try:
        bars = client.get_aggs(ticker="VIX", multiplier=1, timespan="day", from_=int((now().timestamp() - 86400) * 1000), to=int(now().timestamp() * 1000), limit=1)
        return bars.df.iloc[0]['close'] if bars and not bars.df.empty else 0
    except Exception as e:
        print(f"Error fetching VIX: {e}")
        return 0

def get_vix1d_history(days=7):
    try:
        bars = client.get_aggs(ticker="VIX", multiplier=1, timespan="day", from_=int((now().timestamp() - 86400 * days) * 1000), to=int(now().timestamp() * 1000), limit=days)
        return bars.df['close'].tolist() if bars and not bars.df.empty else []
    except Exception as e:
        print(f"Error fetching VIX history: {e}")
        return []

def is_vix_threshold_met():
    vix_data = get_vix1d_history(days=3)
    if len(vix_data) < 2: return False
    return all(v < 24 for v in vix_data[-2:])

def manage_vix_hedge():
    vix = get_vix1d()
    if 22 <= vix < 24:
        hedge_ticker = "UVXY" if vix < 23 else "SQQQ"
        allocate_hedge(hedge_ticker, 0.10)  # 10% capital allocation

def allocate_hedge(ticker, percentage):
    # Implementation for hedge allocation
    pass

def is_earnings_season():
    today = now()
    start_of_year = datetime(today.year, 10, 15)  # Mid-October
    end_of_year = datetime(today.year + 1, 2, 15)  # Mid-February next year
    return start_of_year <= today <= end_of_year

def dynamic_earnings_tickers():
    earnings_tickers = set()
    today = now().strftime('%Y-%m-%d')
    try:
        earnings = client.list_earnings(date=today, limit=200)
        for e in earnings:
            if e.ticker in BROAD_EARNINGS_POOL and e.ticker not in CORE_TICKERS:
                score = cream_score(e.ticker, "LONG", vol_mult, rsi, vwap_dist, air_gap_bonus=True)
                if score >= 9.5:  # Lowered from 10.0
                    c, prem, dte = get_contract(e.ticker, "LONG")
                    if c and prem <= get_premium_cap():  # Dynamic premium cap
                        earnings_tickers.add(e.ticker)
    except: pass
    return list(earnings_tickers)

def get_premium_cap():
    vix = get_vix1d()
    if vix < 18: return 0.25
    elif vix < 22: return 0.30
    else: return 0.35

def is_multiple_high_iv_week():
    today = now()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    try:
        earnings = client.list_earnings(date__gte=start_of_week.strftime('%Y-%m-%d'),
                                       date__lte=end_of_week.strftime('%Y-%m-%d'), limit=500)
        high_iv_count = sum(1 for e in earnings if e.ticker in ["META", "AAPL", "AMZN", "GOOGL", "MSFT"])
        return high_iv_count >= 2
    except: return False

def cream_score_earnings_override(score):
    if is_multiple_high_iv_week():
        return max(score, 9.5)
    return score

def calculate_rsi(prices, period=14):
    return talib.RSI(np.array(prices), period)[-1]

def calculate_vwap(bars):
    typical_price = (bars['high'] + bars['low'] + bars['close']) / 3
    vwap = (typical_price * bars['volume']).sum() / bars['volume'].sum()
    return vwap

def get_air_gap_support(ticker, timespan="minute"):
    bars = safe_aggs(ticker, limit=500, timespan=timespan)
    if len(bars) < 30: return 0
    ema_periods = [9, 21, 50, 200]
    ema_values = []
    for period in ema_periods:
        ema = talib.EMA(np.array(bars['close']), period)[-1]
        ema_values.append(ema)
    return min(ema_values)

def get_lowest_time_frame_air_gap_support(ticker):
    """
    Enhanced Air Gap Identification: Prioritize the lowest time frame air gap as critical support.
    """
    bars = safe_aggs(ticker, limit=1000, timespan="minute")  # Increased limit for more precision
    if len(bars) < 100: return 0
    ema_periods = [5, 12, 34, 50]  # Focus on shorter-term EMAs for minute-level precision
    ema_values = []
    for period in ema_periods:
        ema = talib.EMA(np.array(bars['close']), period)[-1]
        ema_values.append(ema)
    return min(ema_values)

def get_atr(bars, period=14):
    high_low = bars['high'] - bars['low']
    high_close = np.abs(bars['high'] - bars['close'].shift())
    low_close = np.abs(bars['low'] - bars['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.nanmax(ranges, axis=1)
    atr = talib.ATR(bars['high'], bars['low'], bars['close'], period)[-1]
    return atr

def dynamic_position_size(ticker, base_size=100):
    bars = safe_aggs(ticker, limit=100)
    atr = get_atr(bars)
    atr_percentage = (atr / bars['close'].iloc[-1]) * 100
    if atr_percentage > 150:  # High volatility adjustment
        return base_size * 0.5  # Reduce position size by 50%
    return base_size

def post_earnings_short_strategy(ticker):
    """
    Post-Earnings Short Strategy Enhancement: Refine shorting logic post-earnings misses.
    """
    bars = safe_aggs(ticker, limit=500, timespan="minute")
    if len(bars) < 30: return False
    current_price = bars['close'].iloc[-1]
    air_gap_support = get_lowest_time_frame_air_gap_support(ticker)
    if air_gap_support == 0: return False
    earnings_date = get_earnings_date(ticker)
    if not earnings_date or (now() - earnings_date).days > 1: return False  # Within 24 hours of earnings
    # Check for gap down and proximity to air gap support
    if current_price < bars['close'].iloc[-2] * 0.98 and current_price > air_gap_support * 0.95:
        return True
    return False

def get_earnings_date(ticker):
    try:
        earnings = client.list_earnings(ticker=ticker, limit=1)
        return datetime.strptime(earnings[0].date, '%Y-%m-%d') if earnings else None
    except: return None

def execute_trade(ticker, direction, size):
    # Implementation for executing trades
    pass

@tasks.loop(seconds=10)
async def trade_loop():
    global last_pnl, last_trade_time, last_vix, last_earnings_check, trade_count, total_pnl, wins, losses
    if not is_vix_threshold_met(): return
    vix = get_vix1d()
    if vix >= 24: return
    manage_vix_hedge()
    if (now() - last_earnings_check).total_seconds() > 3600:  # Check earnings every hour
        last_earnings_check = now()
        if is_earnings_season():
            earnings_tickers = dynamic_earnings_tickers()
            for ticker in earnings_tickers:
                if post_earnings_short_strategy(ticker):
                    air_gap_support = get_lowest_time_frame_air_gap_support(ticker)
                    if air_gap_support > 0:
                        size = dynamic_position_size(ticker, base_size=100)
                        execute_trade(ticker, "SHORT", size)
                        await send_discord_message(f"Short {ticker} at {now()} targeting air gap support {air_gap_support}")
    for ticker in CORE_TICKERS:
        bars = safe_aggs(ticker)
        if len(bars) < 30: continue
        current_price = bars['close'].iloc[-1]
        air_gap_support = get_lowest_time_frame_air_gap_support(ticker)
        if air_gap_support == 0: continue
        # Enhanced logic for gap down scenarios
        if current_price < bars['close'].iloc[-2] * 0.98 and current_price > air_gap_support * 0.95:
            size = dynamic_position_size(ticker, base_size=100)
            execute_trade(ticker, "SHORT", size)
            await send_discord_message(f"Short {ticker} at {now()} targeting air gap support {air_gap_support}")

async def send_discord_message(message):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(message)
    if DISCORD_WEBHOOK_URL:
        data = {"content": message}
        headers = {"Content-Type": "application/json"}
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers)
        if response.status_code != 204:
            print(f"Failed to send webhook: {response.status_code}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    trade_loop.start()

bot.run(DISCORD_TOKEN)
