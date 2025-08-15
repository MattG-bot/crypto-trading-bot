import time
from bot.risk import get_stop_and_size, calculate_2r_target, calculate_profit_levels, calculate_trailing_stop
from bot.exchange_okx import get_candles, place_order
from bot.config import config, PAPER_TRADING
from bot.safety import safety_manager
from bot.logger import logger, trade_logger
from bot.portfolio import portfolio

open_trades = {}

def enter_trade(symbol, direction, signal_type):
    logger.info(f"💰 Attempting to enter {direction.upper()} trade for {symbol} based on {signal_type} signal.")

    # Safety check before entering trade
    if not safety_manager.should_allow_trading(open_trades):
        logger.warning(f"⚠️  Safety manager blocked trade entry for {symbol}")
        return

    current_price = get_current_price(symbol)
    if current_price is None:
        logger.error(f"❌ Could not get current price for {symbol}, skipping trade entry.")
        return

    candles = get_candles(symbol, bar="1h", limit=100)
    if not candles or 'data' not in candles or len(candles['data']) == 0:
        logger.debug(f"[{symbol}] No 1h candle data, trying 15m instead.")
        candles = get_candles(symbol, bar="15m", limit=100)

    if not candles or 'data' not in candles or len(candles['data']) == 0:
        logger.error(f"[{symbol}] No candle data available, skipping trade entry.")
        return

    logger.debug(f"[{symbol}] Received {len(candles.get('data', []))} candles")

    sizing = get_stop_and_size(symbol, current_price, direction, candles)
    if sizing["size"] <= 0:
        logger.warning(f"⚠️  Trade sizing for {symbol} is zero or invalid, skipping trade.")
        return

    # Additional safety validation on position size
    if not safety_manager.validate_trade_size(symbol, sizing["size"], current_price):
        logger.warning(f"⚠️  Safety manager rejected trade size for {symbol}")
        return

    # Skip OKX validation for now to avoid API issues
    logger.info(f"🔄 Using simplified approach - skipping OKX pre-validation for {symbol}")
    
    # Paper trading mode
    if PAPER_TRADING:
        logger.info(f"📝 [PAPER] Would enter {direction.upper()} trade on {symbol}")
        order_response = {"code": "0", "data": [{"ordId": f"paper_{symbol}_{int(time.time())}"}]}
    else:
        # Convert direction to OKX side format
        okx_side = "buy" if direction == "long" else "sell"
        order_response = place_order(symbol, okx_side, sizing["size"])

    # Check for different types of failures
    if order_response and order_response.get("code") == "0":
        # Order succeeded
        pass
    elif order_response and order_response.get("code") == "margin_validation_failed":
        logger.warning(f"⚠️ {symbol} trade skipped - real-time margin validation failed")
        trade_logger.warning(f"MARGIN_FAIL | {symbol} | {direction.upper()} | ${current_price} | {order_response.get('msg', 'Unknown margin error')}")
        return
    else:
        # Other failure
        logger.error(f"❌ Failed to place order for {symbol}: {order_response}")
        return

    if order_response and order_response.get("code") == "0":
        stop_loss = sizing["stop_loss"]
        profit_levels = calculate_profit_levels(current_price, stop_loss, direction)
        take_profit = profit_levels["2R"]  # Define for backward compatibility and logging
        
        position_data = {
            "direction": direction,
            "entry_price": current_price,
            "size": sizing["size"],
            "original_size": sizing["size"],  # Track original size for partial exits
            "stop_loss": stop_loss,
            "take_profit": take_profit,  # Use the defined variable
            "profit_levels": profit_levels,
            "profits_taken": {  # Track which profit levels have been hit
                "1R": False,
                "2R": False, 
                "3R": False,
                "4R": False
            },
            "high_water_mark": current_price,  # Track highest price for trailing stops
            "trailing_stop_active": False,
            "atr": sizing["atr"],  # Store ATR for trailing calculations
            "signal_type": signal_type,
            "opened_at": time.time(),
            "paper_trade": PAPER_TRADING
        }
        
        open_trades[symbol] = position_data
        
        # Save to persistent storage
        from bot.position_storage import position_storage
        position_storage.save_position(symbol, position_data)
        
        trade_mode = "[PAPER]" if PAPER_TRADING else "[LIVE]"
        logger.info(f"✅ {trade_mode} Entered {direction.upper()} trade on {symbol} at ${current_price}")
        logger.info(f"   📊 Size: {sizing['size']}, TP: ${take_profit}, SL: ${stop_loss}")
        trade_logger.info(f"ENTER | {symbol} | {direction.upper()} | ${current_price} | Size: {sizing['size']} | TP: ${take_profit} | SL: ${stop_loss} | {signal_type}")
    else:
        logger.error(f"❌ Failed to place order for {symbol}: {order_response}")


def check_and_close_trades():
    to_close = []

    for symbol, trade in open_trades.items():
        current_price = get_current_price(symbol)
        if current_price is None:
            logger.warning(f"⚠️  Could not get current price for {symbol}, skipping exit check.")
            continue
            
        direction = trade["direction"]
        entry_price = trade["entry_price"]
        sl = trade["stop_loss"]
        
        # Skip if stop loss is not set
        if sl is None:
            logger.warning(f"⚠️  {symbol} missing stop loss, skipping exit check")
            continue
        
        # Update high water mark for trailing stops
        if direction == "long" and current_price > trade.get("high_water_mark", entry_price):
            trade["high_water_mark"] = current_price
        elif direction == "short" and current_price < trade.get("high_water_mark", entry_price):
            trade["high_water_mark"] = current_price
        
        # Calculate current P&L
        if direction == "long":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Check for staged profit taking
        profit_levels = trade.get("profit_levels", {})
        profits_taken = trade.get("profits_taken", {})
        atr = trade.get("atr", 0)
        
        # Process profit levels in order: 1R, 2R, 3R, 4R
        for level in ["1R", "2R", "3R", "4R"]:
            if level in profit_levels and not profits_taken.get(level, False):
                target_price = profit_levels[level]
                
                # Check if profit level hit
                hit_target = False
                if direction == "long" and current_price >= target_price:
                    hit_target = True
                elif direction == "short" and current_price <= target_price:
                    hit_target = True
                
                if hit_target:
                    # Take partial profit (25% of remaining position)
                    current_size = trade["size"]
                    exit_size = round(current_size * 0.25, 4)
                    remaining_size = round(current_size - exit_size, 4)
                    
                    logger.info(f"🎯 {level} profit level hit for {symbol} at ${current_price}")
                    logger.info(f"   💰 Taking 25% profit: {exit_size} (remaining: {remaining_size})")
                    
                    # Execute partial exit
                    if take_partial_profit(symbol, exit_size, level, current_price, pnl_pct):
                        trade["size"] = remaining_size
                        profits_taken[level] = True
                        trade["profits_taken"] = profits_taken
                        
                        # Update stop loss after profit taking
                        if level == "1R":
                            trade["stop_loss"] = entry_price  # Move to breakeven
                            logger.info(f"   🛡️  Stop loss moved to breakeven: ${entry_price}")
                        elif level == "2R":
                            trade["stop_loss"] = profit_levels["1R"]  # Move to +1R
                            logger.info(f"   🛡️  Stop loss moved to +1R: ${profit_levels['1R']}")
                        elif level == "3R":
                            trade["stop_loss"] = profit_levels["2R"]  # Move to +2R
                            logger.info(f"   🛡️  Stop loss moved to +2R: ${profit_levels['2R']}")
                        elif level == "4R":
                            # Activate trailing stop after 4R
                            trade["trailing_stop_active"] = True
                            logger.info(f"   📈 Trailing stop activated for remaining 25%")
                        
                        # Update persistent storage
                        from bot.position_storage import position_storage
                        position_storage.save_position(symbol, trade)
                    
                    break  # Process one level at a time

        # Handle trailing stop for remaining position after 4R
        if trade.get("trailing_stop_active", False) and atr > 0:
            high_water_mark = trade.get("high_water_mark", entry_price)
            trailing_sl = calculate_trailing_stop(current_price, high_water_mark, atr, direction)
            
            # Update trailing stop if it's better than current stop
            if direction == "long" and trailing_sl > trade["stop_loss"]:
                trade["stop_loss"] = trailing_sl
                logger.debug(f"📈 {symbol} trailing stop updated to ${trailing_sl}")
            elif direction == "short" and trailing_sl < trade["stop_loss"]:
                trade["stop_loss"] = trailing_sl
                logger.debug(f"📈 {symbol} trailing stop updated to ${trailing_sl}")

        # Check stop loss
        exit_reason = None
        if direction == "long" and current_price <= trade["stop_loss"]:
            exit_reason = "STOP_LOSS"
            logger.info(f"🛑 Stop loss hit for {symbol} at ${current_price} (P&L: {pnl_pct:.2f}%)")
        elif direction == "short" and current_price >= trade["stop_loss"]:
            exit_reason = "STOP_LOSS"
            logger.info(f"🛑 Stop loss hit for {symbol} at ${current_price} (P&L: {pnl_pct:.2f}%)")

        # Close remaining position if stop loss hit
        if exit_reason:
            close_trade(symbol, exit_reason, current_price, pnl_pct)
            to_close.append(symbol)
            
            # Update safety manager with trade result
            trade_result = "profit" if pnl_pct > 0 else "loss"
            safety_manager.check_consecutive_losses(trade_result)

    for sym in to_close:
        open_trades.pop(sym, None)
        
        # Remove from persistent storage
        from bot.position_storage import position_storage
        position_storage.remove_position(sym)

def take_partial_profit(symbol, exit_size, profit_level, exit_price, pnl_pct):
    """
    Execute partial profit taking for a specific profit level.
    Returns True if successful, False otherwise.
    """
    if symbol not in open_trades:
        logger.warning(f"⚠️  No open trade found for {symbol} to take partial profit.")
        return False

    trade = open_trades[symbol]
    direction = trade["direction"]
    
    trade_mode = "[PAPER]" if trade.get("paper_trade", False) else "[LIVE]"
    logger.info(f"💰 {trade_mode} Taking {profit_level} partial profit for {symbol}")

    # Paper trading mode
    if trade.get("paper_trade", False):
        logger.info(f"📝 [PAPER] Would take partial profit on {symbol}: {exit_size}")
        response = {"code": "0", "data": [{"ordId": f"paper_partial_{symbol}_{int(time.time())}"}]}
    else:
        response = place_order(
            symbol,
            "sell" if direction == "long" else "buy",
            exit_size,
            reduce_only=True
        )
    
    if response and response.get("code") == "0":
        # Calculate trade duration and profit
        duration_minutes = (time.time() - trade["opened_at"]) / 60
        profit_amount = exit_size * (exit_price - trade["entry_price"]) if direction == "long" else exit_size * (trade["entry_price"] - exit_price)
        
        logger.info(f"✅ {trade_mode} Partial profit taken for {symbol} at {profit_level}")
        logger.info(f"   📈 Size: {exit_size} | Price: ${exit_price} | Profit: ${profit_amount:.2f}")
        
        trade_logger.info(f"PARTIAL_EXIT | {symbol} | {profit_level} | ${exit_price} | Size: {exit_size} | Profit: ${profit_amount:.2f} | Duration: {duration_minutes:.0f}m")
        
        # Record partial trade in portfolio tracker (only for live trades)
        if not trade.get("paper_trade", False):
            try:
                portfolio.record_trade(
                    symbol=symbol,
                    direction=direction,
                    entry_price=trade["entry_price"],
                    exit_price=exit_price,
                    size=exit_size,
                    exit_reason=f"PARTIAL_{profit_level}",
                    signal_type=trade.get("signal_type", "unknown"),
                    duration_minutes=duration_minutes
                )
            except Exception as e:
                logger.error(f"❌ Error recording partial trade in portfolio: {e}")
        
        return True
    else:
        logger.error(f"❌ Failed to take partial profit for {symbol}: {response}")
        return False

def close_trade(symbol, exit_reason="MANUAL", exit_price=None, pnl_pct=None):
    if symbol not in open_trades:
        logger.warning(f"⚠️  No open trade found for {symbol} to close.")
        return

    trade = open_trades[symbol]
    direction = trade["direction"]
    size = trade["size"]
    entry_price = trade["entry_price"]
    
    trade_mode = "[PAPER]" if trade.get("paper_trade", False) else "[LIVE]"
    logger.info(f"🔄 {trade_mode} Closing {direction.upper()} trade for {symbol}")

    # Paper trading mode
    if trade.get("paper_trade", False):
        logger.info(f"📝 [PAPER] Would close {direction.upper()} trade on {symbol}")
        response = {"code": "0", "data": [{"ordId": f"paper_close_{symbol}_{int(time.time())}"}]}
    else:
        response = place_order(
            symbol,
            "sell" if direction == "long" else "buy",
            size,
            reduce_only=True
        )
    
    if response and response.get("code") == "0":
        # Calculate trade duration
        duration_minutes = (time.time() - trade["opened_at"]) / 60
        
        logger.info(f"✅ {trade_mode} Trade closed for {symbol}")
        if pnl_pct is not None:
            logger.info(f"   📈 P&L: {pnl_pct:.2f}% | Duration: {duration_minutes:.0f}m")
        
        trade_logger.info(f"CLOSE | {symbol} | {exit_reason} | ${exit_price or 'N/A'} | P&L: {pnl_pct or 'N/A'}% | Duration: {duration_minutes:.0f}m")
        
        # Record trade in portfolio tracker (only for completed trades with known exit price)
        if exit_price is not None and not trade.get("paper_trade", False):
            try:
                portfolio.record_trade(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    size=size,
                    exit_reason=exit_reason,
                    signal_type=trade.get("signal_type", "unknown"),
                    duration_minutes=duration_minutes
                )
            except Exception as e:
                logger.error(f"❌ Error recording trade in portfolio: {e}")
    else:
        logger.error(f"❌ Failed to close trade for {symbol}: {response}")

def get_current_price(symbol):
    """
    Get current market price for a symbol using OKX ticker API.
    """
    try:
        from bot.exchange_okx import get_ticker
        ticker_data = get_ticker(symbol)
        
        if ticker_data.get("code") == "0" and ticker_data.get("data"):
            price = float(ticker_data["data"][0]["last"])
            print(f"[{symbol}] Current price: {price}")
            return price
        else:
            print(f"[{symbol}] Failed to get ticker: {ticker_data}")
            return None
            
    except Exception as e:
        print(f"[{symbol}] Error getting current price: {e}")
        return None
