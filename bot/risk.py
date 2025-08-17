import json
import pandas as pd
from bot.config import config
from bot.exchange_okx import get_account_equity
from bot.logger import logger

def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR) using the correct formula.
    True Range = max(high-low, high-prev_close, prev_close-low)
    """
    df['prev_close'] = df['c'].shift(1)
    
    # Calculate the three components of True Range
    df['hl'] = df['h'] - df['l']  # High - Low
    df['hc'] = abs(df['h'] - df['prev_close'])  # High - Previous Close
    df['lc'] = abs(df['l'] - df['prev_close'])  # Low - Previous Close
    
    # True Range is the maximum of the three
    df['tr'] = df[['hl', 'hc', 'lc']].max(axis=1)
    
    # ATR is the moving average of True Range
    df['atr'] = df['tr'].rolling(window=period).mean()
    
    # Return the most recent ATR value
    latest_atr = df['atr'].iloc[-1]
    
    # Additional validation for traditional assets
    if pd.isna(latest_atr) or latest_atr <= 0:
        logger.warning(f"ATR calculation failed, latest_atr: {latest_atr}")
        return None
        
    return latest_atr

def calculate_profit_levels(entry_price, stop_loss, direction="long"):
    """
    Calculate staged profit levels: 1R, 2R, 3R, 4R from entry.
    Returns dict with profit levels for partial exits.
    """
    risk = abs(entry_price - stop_loss)
    
    # Use higher precision for memecoins (very small prices)
    precision = 10 if entry_price < 0.001 else 6
    
    if direction == "long":
        levels = {
            "1R": round(entry_price + 1 * risk, precision),
            "2R": round(entry_price + 2 * risk, precision), 
            "3R": round(entry_price + 3 * risk, precision),
            "4R": round(entry_price + 4 * risk, precision)
        }
    else:
        levels = {
            "1R": round(entry_price - 1 * risk, precision),
            "2R": round(entry_price - 2 * risk, precision),
            "3R": round(entry_price - 3 * risk, precision),
            "4R": round(entry_price - 4 * risk, precision)
        }
    
    return levels

def calculate_2r_target(entry_price, stop_loss, direction="long"):
    """
    Backward compatibility - calculate 2R target.
    """
    levels = calculate_profit_levels(entry_price, stop_loss, direction)
    return levels["2R"]

def calculate_trailing_stop(current_price, high_water_mark, atr, direction="long"):
    """
    Calculate trailing stop loss based on ATR.
    """
    trailing_distance = atr * 2  # 2x ATR trailing distance
    
    if direction == "long":
        return round(high_water_mark - trailing_distance, 6)
    else:
        return round(high_water_mark + trailing_distance, 6)

import pandas as pd

def get_stop_and_size(symbol, entry_price, direction="long", candles=None):
    print(f"[{symbol} - get_stop_and_size] Received candles type: {type(candles)}")
    if isinstance(candles, dict):
        print(f"[{symbol} - get_stop_and_size] Keys: {list(candles.keys())}")
    else:
        print(f"[{symbol} - get_stop_and_size] Content sample: {candles.head() if hasattr(candles, 'head') else candles}")

    if candles is None:
        print(f"{symbol}: No candles passed to get_stop_and_size")
        return {"size": 0, "atr": 0, "stop_loss": entry_price, "risk_amount": 0}

    if not candles or 'data' not in candles or len(candles['data']) == 0:
        print(f"{symbol}: No candle data for sizing")
        return {"size": 0, "atr": 0, "stop_loss": entry_price, "risk_amount": 0}

    candle_data = candles['data']
    columns = ['ts', 'o', 'h', 'l', 'c', 'vol', 'vol_ccy', 'vol_usd', 'confirm']
    df = pd.DataFrame(candle_data, columns=columns)
    df = df.astype({'h': float, 'l': float, 'c': float})

    # ATR calculation with enhanced validation for traditional assets
    atr = calculate_atr(df, period=14)

    # For traditional crypto assets, ATR should never fail - add robust validation
    if atr is None or atr == 0:
        logger.error(f"[{symbol}] ATR calculation completely failed for traditional asset")
        # For traditional assets, use recent price volatility as emergency fallback
        recent_high = df['h'].tail(5).max()
        recent_low = df['l'].tail(5).min()
        price_volatility = recent_high - recent_low
        atr = price_volatility / 5  # Average daily range over 5 periods
        logger.warning(f"[{symbol}] Emergency ATR fallback: {atr:.8f} (based on recent volatility)")
    
    # Add safety bounds for traditional assets to prevent extreme position sizes
    min_atr = entry_price * 0.005  # Minimum 0.5% of entry price
    max_atr = entry_price * 0.05   # Maximum 5% of entry price
    
    if atr < min_atr:
        logger.warning(f"[{symbol}] ATR too small ({atr:.8f}), using minimum: {min_atr:.8f}")
        atr = min_atr
    elif atr > max_atr:
        logger.warning(f"[{symbol}] ATR too large ({atr:.8f}), using maximum: {max_atr:.8f}")
        atr = max_atr
    
    logger.info(f"[{symbol}] Final ATR: {atr:.8f} ({(atr/entry_price)*100:.2f}% of entry price)")
    
    if atr <= 0:
        logger.error(f"{symbol}: ATR validation failed completely")
        return {"size": 0, "atr": 0, "stop_loss": entry_price, "risk_amount": 0}

    # Get actual margin information instead of just equity
    from bot.exchange_okx import get_account_margin_info
    margin_info = get_account_margin_info()
    
    if margin_info:
        # Use available margin for sizing instead of total equity
        available_margin = margin_info['availBal']
        total_equity = margin_info['totalEq']
        used_margin = margin_info['used_margin']
        
        logger.info(f"[{symbol}] Margin Status - Available: ${available_margin:.2f}, Used: ${used_margin:.2f}, Total: ${total_equity:.2f}")
        
        # Use available margin as the base for risk calculations
        equity = available_margin  # This is what we can actually use for new trades
    else:
        # Fallback to old method if margin info fails
        equity = get_account_equity()
        available_margin = equity  # Set for later use in calculations
        logger.warning(f"[{symbol}] Using fallback equity calculation: ${equity:.2f}")
    
    # Define memecoin symbols
    memecoins = config.get('memecoins', [])
    
    # PURE PERPETUAL FUTURES STRATEGY - Margin allocation first
    
    # Step 1: Allocate fixed margin per position (consistent across all assets)
    margin_per_position_pct = config.get('margin_per_position_pct', 0.10)  # 10% of available margin per position
    
    # Special allocations for different asset classes
    if symbol == 'BTC-USDT-SWAP':
        btc_allocation_pct = config.get('btc_margin_per_position_pct', 0.05)  # 5% for BTC
        target_margin = available_margin * btc_allocation_pct
        logger.info(f"[{symbol}] Using enhanced BTC allocation: {btc_allocation_pct*100:.0f}%")
    elif symbol in memecoins:
        memecoin_allocation_pct = config.get('memecoin_margin_per_position_pct', 0.025)  # 2.5% for memecoins
        target_margin = available_margin * memecoin_allocation_pct
        logger.info(f"[{symbol}] Using memecoin allocation: {memecoin_allocation_pct*100:.1f}%")
    else:
        target_margin = available_margin * margin_per_position_pct
    
    # Validate against actual OKX data
    if margin_info:
        actual_available = margin_info['availBal']
        logger.info(f"[{symbol}] OKX MARGIN VALIDATION:")
        logger.info(f"  OKX Available Margin: ${actual_available:.2f}")
        logger.info(f"  Target Allocation: {margin_per_position_pct*100:.0f}% = ${target_margin:.2f}")
        logger.info(f"  Portfolio Utilization: {(target_margin/actual_available)*100:.1f}% per position")
        
        # Double-check our calculation is based on real OKX data
        if abs(available_margin - actual_available) > 1:
            logger.warning(f"[{symbol}] Margin mismatch - Using: ${available_margin:.2f}, OKX Shows: ${actual_available:.2f}")
            # Use the actual OKX value
            available_margin = actual_available
            target_margin = available_margin * margin_per_position_pct
            logger.info(f"[{symbol}] Corrected target margin: ${target_margin:.2f}")
    else:
        logger.warning(f"[{symbol}] Could not validate against OKX margin data")
    
    # Step 2: Get leverage (actual from OKX - user set to 10x for all instruments)
    # Conservative estimates matching user's OKX leverage settings
    leverage_estimates = {
        'BTC-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'ETH-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'SOL-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'XRP-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'LTC-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'ADA-USDT-SWAP': 10,   # User set to 10x leverage in OKX
        'AVAX-USDT-SWAP': 10,  # User set to 10x leverage in OKX
        'LINK-USDT-SWAP': 10,  # User set to 10x leverage in OKX
        'NEAR-USDT-SWAP': 10   # User set to 10x leverage in OKX
    }
    
    # Use only conservative fixed estimates - no OKX queries to avoid API errors
    estimated_leverage = leverage_estimates.get(symbol, 10)
    logger.info(f"[{symbol}] Using FIXED estimate: {estimated_leverage}x (simplified approach)")
    
    # Step 3: Calculate position size from margin allocation (NOT from risk/stop loss)
    # Account for actual contract specifications from OKX
    
    # OKX Contract Specifications (1 contract = X units of underlying asset)
    contract_multipliers = {
        'BTC-USDT-SWAP': 0.01,    # 1 contract = 0.01 BTC
        'ETH-USDT-SWAP': 0.1,     # 1 contract = 0.1 ETH  
        'SOL-USDT-SWAP': 1.0,     # 1 contract = 1 SOL
        'XRP-USDT-SWAP': 100.0,   # 1 contract = 100 XRP
        'LTC-USDT-SWAP': 1.0,     # 1 contract = 1 LTC
        'ADA-USDT-SWAP': 100.0,   # 1 contract = 100 ADA
        'AVAX-USDT-SWAP': 1.0,    # 1 contract = 1 AVAX
        'LINK-USDT-SWAP': 1.0,    # 1 contract = 1 LINK
        'NEAR-USDT-SWAP': 10.0,   # 1 contract = 10 NEAR
        
        # Memecoins - adjusted for proper $1000 position sizing
        'BONK-USDT-SWAP': 1000000.0,   # 1 contract = 1M BONK
        'PEPE-USDT-SWAP': 1000000.0,   # 1 contract = 1M PEPE  
        'PENGU-USDT-SWAP': 1000.0,     # 1 contract = 1K PENGU
    }
    
    contract_multiplier = contract_multipliers.get(symbol, 1.0)
    
    # Calculate notional value needed
    notional_position_value = target_margin * estimated_leverage
    
    # Calculate contracts needed: Notional Value / (Entry Price × Contract Multiplier)  
    # This accounts for how many units of underlying asset each contract represents
    size = notional_position_value / (entry_price * contract_multiplier)
    
    # OKX Position Limits - prevent exceeding exchange maximums
    okx_position_limits = {
        'BTC-USDT-SWAP': 100000,      # Max 100k contracts
        'ETH-USDT-SWAP': 100000,      # Max 100k contracts
        'SOL-USDT-SWAP': 50000,       # Max 50k contracts
        'XRP-USDT-SWAP': 10000,       # Max 10k contracts
        'LTC-USDT-SWAP': 50000,       # Max 50k contracts
        'ADA-USDT-SWAP': 10000,       # Max 10k contracts
        'AVAX-USDT-SWAP': 50000,      # Max 50k contracts
        'LINK-USDT-SWAP': 50000,      # Max 50k contracts
        'NEAR-USDT-SWAP': 50000,      # Max 50k contracts
        
        # Memecoins - much lower limits due to volatility
        'BONK-USDT-SWAP': 100,        # Max 100 contracts (100M BONK)
        'PEPE-USDT-SWAP': 100,        # Max 100 contracts (100M PEPE)
        'PENGU-USDT-SWAP': 1000,      # Max 1000 contracts (1M PENGU)
    }
    
    max_contracts = okx_position_limits.get(symbol, 10000)  # Default 10k limit
    if size > max_contracts:
        logger.warning(f"[{symbol}] Position size {size:.2f} exceeds OKX limit {max_contracts}, reducing to limit")
        size = max_contracts
        # Recalculate notional and margin with reduced size
        notional_position_value = size * entry_price * contract_multiplier
    
    logger.info(f"[{symbol}] PURE PERPETUAL SIZING:")
    logger.info(f"  Target Margin: ${target_margin:.2f} (fixed allocation)")
    logger.info(f"  Leverage: {estimated_leverage}x")
    logger.info(f"  Contract Multiplier: {contract_multiplier} units per contract")
    logger.info(f"  Notional Value: ${notional_position_value:.2f}")
    logger.info(f"  Position Size: {size:.4f} contracts")
    logger.info(f"  Actual Units: {size * contract_multiplier:.6f} {symbol.split('-')[0]}")
    
    # Step 4: Calculate ATR-based stop loss (independent of position sizing)
    # Use configured stop loss multiplier
    sl_multiplier = config.get('atr', {}).get('stop_loss_multiplier', 2)
    sl_distance = atr * sl_multiplier
    
    if direction == "long":
        stop_loss = entry_price - sl_distance
    else:
        stop_loss = entry_price + sl_distance
    
    price_diff = abs(entry_price - stop_loss)
    
    # Step 5: Calculate actual risk based on position size and stop distance
    # Risk = Position Size × Price Difference (this is what we'll actually lose)
    risk_amount = size * price_diff
    
    logger.info(f"[{symbol}] STOP LOSS & RISK:")
    logger.info(f"  ATR: {atr:.8f} × {sl_multiplier} = ${sl_distance:.8f}")
    logger.info(f"  Stop Loss: ${stop_loss:.2f}")
    logger.info(f"  Price Difference: ${price_diff:.8f}")
    logger.info(f"  Actual Risk: ${risk_amount:.2f} (what we'll lose if stopped out)")
    
    # Safety check - ensure stop loss is reasonable
    min_price_diff = entry_price * 0.005  # Minimum 0.5% of entry price
    max_price_diff = entry_price * 0.08   # Maximum 8% of entry price
    
    if price_diff < min_price_diff:
        price_diff = min_price_diff
        if direction == "long":
            stop_loss = entry_price - price_diff
        else:
            stop_loss = entry_price + price_diff
        # Recalculate risk with adjusted stop
        risk_amount = size * price_diff
        logger.warning(f"[{symbol}] Stop loss too tight, adjusted to ${stop_loss:.2f} (risk: ${risk_amount:.2f})")
    
    elif price_diff > max_price_diff:
        price_diff = max_price_diff
        if direction == "long":
            stop_loss = entry_price - price_diff
        else:
            stop_loss = entry_price + price_diff
        # Recalculate risk with adjusted stop
        risk_amount = size * price_diff
        logger.warning(f"[{symbol}] Stop loss too wide, adjusted to ${stop_loss:.2f} (risk: ${risk_amount:.2f})")

    # Final validation - ensure margin usage is within bounds
    actual_position_value = size * entry_price
    actual_margin_estimate = actual_position_value / estimated_leverage
    
    # Safety check: Don't allow position to use more than 25% of available margin
    # EXCEPTION: BTC gets enhanced allocation and is exempt from this safety limit
    if symbol != 'BTC-USDT-SWAP':
        max_margin_per_position = available_margin * 0.25
        if actual_margin_estimate > max_margin_per_position:
            logger.warning(f"[{symbol}] Position margin too high: ${actual_margin_estimate:.2f} > ${max_margin_per_position:.2f}")
            # Reduce position size to fit margin limit
            size = (max_margin_per_position * estimated_leverage) / entry_price
            # Recalculate actual risk with reduced size
            risk_amount = size * price_diff
            logger.info(f"[{symbol}] Reduced position: Size {size:.4f}, Risk: ${risk_amount:.2f}")
    else:
        logger.info(f"[{symbol}] BTC exempt from 25% safety limit - using enhanced allocation")
    
    logger.info(f"[{symbol}] FINAL POSITION:")
    logger.info(f"  Size: {size:.4f} contracts")
    logger.info(f"  Notional: ${size * entry_price * contract_multiplier:.2f}")
    logger.info(f"  Margin: ${(size * entry_price * contract_multiplier / estimated_leverage):.2f}")
    logger.info(f"  Stop Loss: ${stop_loss:.2f}")
    logger.info(f"  Risk if Stopped: ${risk_amount:.2f}")
    
    # Verify position value with correct contract multiplier
    actual_position_value = size * entry_price * contract_multiplier
    logger.info(f"[{symbol}] Position Check - Risk: ${risk_amount:.2f}, Position: ${actual_position_value:.2f}, Size: {size:.4f}")
    
    if size <= 0:
        size = 0

    # Debug logging
    logger.info(f"[{symbol}] DEBUG - Entry: ${entry_price}, Risk: ${risk_amount:.2f}, ATR: {atr:.4f}")
    logger.info(f"[{symbol}] DEBUG - SL Distance: {sl_distance:.4f}, Stop Loss: ${stop_loss:.4f}")
    logger.info(f"[{symbol}] DEBUG - Price Diff: {price_diff:.4f}, Calculated Size: {size:.4f}")
    
    return {
        "size": round(size, 4),  # Increased precision from 2 to 4 decimal places
        "atr": atr,
        "stop_loss": round(stop_loss, 6),
        "risk_amount": round(risk_amount, 2)
    }

