import os
import requests
import json
from datetime import datetime, timedelta
import discord
from discord.ext import tasks, commands
import talib
import numpy as np
import pandas as pd
import alpaca_trade_api as tradeapi

# Discord bot and webhook setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.environ.get('DISCORD_CHANNEL_ID'))
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# Alpaca API setup
API_KEY = os.environ.get('ALPACA_API_KEY')
API_SECRET = os.environ.get('ALPACA_API_SECRET')
BASE_URL = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
client = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL, api_version='v2')

@tasks.loop(minutes=5)
async def check_stock():
    try:
        # Get stock data
        symbol = 'TSLA'
        bars = client.get_barset(symbol, '1Min', limit=100)
        data = bars[symbol]
        
        # Convert to DataFrame
        df = pd.DataFrame({
            'close': [bar.c for bar in data],
            'high': [bar.h for bar in data],
            'low': [bar.l for bar in data],
            'open': [bar.o for bar in data],
            'volume': [bar.v for bar in data]
        })
        
        # Calculate indicators
        rsi = talib.RSI(df['close'], timeperiod=14)
        ema5 = talib.EMA(df['close'], timeperiod=5)
        ema12 = talib.EMA(df['close'], timeperiod=12)
        ema34 = talib.EMA(df['close'], timeperiod=34)
        ema50 = talib.EMA(df['close'], timeperiod=50)
        
        # Air-gap analysis
        air_gaps = {
            '5/12': ema5.iloc[-1] - ema12.iloc[-1],
            '12/34': ema12.iloc[-1] - ema34.iloc[-1],
            '34/50': ema34.iloc[-1] - ema50.iloc[-1]
        }
        
        # Earnings check
        earnings_date = get_earnings_date(symbol)
        if earnings_date and (earnings_date - datetime.now()).days < 7:
            message = f'Upcoming earnings for {symbol} on {earnings_date}. Current air gaps: {air_gaps}'
        else:
            message = f'Current air gaps for {symbol}: {air_gaps}'
        
        # Send to Discord
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        await channel.send(message)
        
    except Exception as e:
        print(f'Error: {e}')

def get_earnings_date(symbol):
    # Placeholder for earnings date retrieval
    url = f'https://financialmodelingprep.com/api/v3/earning_calendar?symbol={symbol}&apikey={os.environ.get('FMP_API_KEY')}'
    response = requests.get(url)
    data = response.json()
    if data and 'earningsDate' in data[0]:
        return datetime.strptime(data[0]['earningsDate'], '%Y-%m-%d')
    return None

check_stock.start()
bot.run(DISCORD_TOKEN)
