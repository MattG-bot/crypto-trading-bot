# bot/strategy.py

import pandas as pd
import numpy as np
from ta.volatility import BollingerBands
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator

def analyze_signal(symbol, candles, config):
    if candles is None:
        print(f"[{symbol}] No candles received, skipping.")
        return None, None

    candle_data = candles.get('data')
    if not candle_data or len(candle_data) < 30:
        print(f"[{symbol}] Not enough candle data, skipping.")
        return None, None

    columns = ['ts', 'o', 'h', 'l', 'c', 'vol', 'vol_ccy', 'vol_usd', 'confirm']
    df = pd.DataFrame(candle_data, columns=columns)
    df = df.iloc[::-1]  # oldest first
    df = df.astype({'c': float, 'h': float, 'l': float, 'vol': float})

    # --- Indicators ---
    rsi = RSIIndicator(close=df['c'], window=config['rsi']['period']).rsi()
    ema = EMAIndicator(close=df['c'], window=config['ema']['period']).ema_indicator()
    macd_indicator = MACD(df['c'])
    macd_line = macd_indicator.macd()
    macd_signal = macd_indicator.macd_signal()
    bb = BollingerBands(close=df['c'], window=config['bollinger_bands']['period'], window_dev=config['bollinger_bands']['std_dev'])
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_width = bb.bollinger_wband()
    volume_ma = df['vol'].rolling(20).mean()
    volume_ratio = df['vol'].iloc[-1] / volume_ma.iloc[-1] if volume_ma.iloc[-1] != 0 else 0

    price = df['c'].iloc[-1]
    rsi_now = rsi.iloc[-1]
    ema_now = ema.iloc[-1]
    macd_now = macd_line.iloc[-1]
    macd_sig = macd_signal.iloc[-1]
    bb_upper_now = bb_upper.iloc[-1]
    bb_lower_now = bb_lower.iloc[-1]
    bbw_now = bb_width.iloc[-1]

    # --- Flags ---
    price_above_ema = price > ema_now
    price_below_ema = price < ema_now
    macd_cross_up = macd_now > macd_sig
    macd_cross_down = macd_now < macd_sig
    volume_confirmed = volume_ratio > config['volume']['confirm_ratio']
    strong_volume = volume_ratio > config['volume']['strong_ratio']

    # --- Memecoin Strategy ---
    if symbol in config['memecoins']:
        bb_breakout_up = price > bb_upper_now and (price / bb_upper_now) > 1 + config['bollinger_bands']['breakout_momentum_pct'] / 100
        bb_breakout_down = price < bb_lower_now and (bb_lower_now / price) > 1 + config['bollinger_bands']['breakout_momentum_pct'] / 100
        if volume_ratio > config['volume']['memecoin_ratio']:
            if bb_breakout_up:
                return 'long', 'memecoin'
            elif bb_breakout_down:
                return 'short', 'memecoin'

    # --- Traditional Strategy ---
    if (rsi_now < config['rsi']['long_threshold'] and price_above_ema and volume_confirmed) or \
       (rsi_now < 55 and price_above_ema and macd_cross_up and volume_confirmed):
        return 'long', 'traditional'

    if (rsi_now > config['rsi']['short_threshold'] and price_below_ema and volume_confirmed) or \
       (rsi_now > 45 and price_below_ema and macd_cross_down and volume_confirmed):
        return 'short', 'traditional'

    # --- Momentum Strategy ---
    if price_above_ema and macd_cross_up and rsi_now > config['rsi']['momentum_long']:
        return 'long', 'momentum'

    if price_below_ema and macd_cross_down and rsi_now < config['rsi']['momentum_short']:
        return 'short', 'momentum'

    return None, None

