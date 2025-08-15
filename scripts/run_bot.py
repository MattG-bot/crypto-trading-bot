# scripts/run_bot.py

import time
import sys
from bot.config import TRADING_SYMBOLS, config, validate_config, PAPER_TRADING
from bot.logger import logger, trade_logger
from bot.exchange_okx import get_candles
from bot.strategy import analyze_signal
from bot.trade_executor import enter_trade, check_and_close_trades, open_trades
from bot.sync import position_sync
from bot.safety import safety_manager
from bot.portfolio import portfolio
from bot.position_migration import migrate_all_positions

def run_strategy_loop():
    logger.info("🤖 Crypto Trading Bot Starting...")
    logger.info(f"📊 Paper Trading: {'ON' if PAPER_TRADING else 'OFF'}")
    logger.info(f"🎯 Trading Symbols: {TRADING_SYMBOLS}")
    
    # Initial position synchronization
    if not PAPER_TRADING:
        logger.info("🔄 Performing initial position sync...")
        position_sync.force_sync()
        
        # Migrate existing positions to staged profit format
        logger.info("🔄 Migrating positions to staged profit format...")
        migrate_all_positions(open_trades)
        
        # Display position summary
        summary = position_sync.get_position_summary()
        logger.info(f"📊 Initial positions: {summary['total_positions']} | Unrealized P&L: ${summary['unrealized_pnl']:.2f}")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        cycle_time = time.strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"🔄 Cycle #{cycle_count} - Checking signals @ {cycle_time}")

        # Track cycle statistics
        signals_found = 0
        errors_count = 0

        for symbol in TRADING_SYMBOLS:
            if symbol in open_trades:
                logger.debug(f"🕒 Skipping {symbol} — already in trade")
                continue

            try:
                logger.debug(f"📈 Analyzing {symbol}...")
                candles = get_candles(symbol, bar="15m", limit=100)
                
                if not candles or 'data' not in candles:
                    logger.warning(f"⚠️  No candle data received for {symbol}")
                    continue
                
                logger.debug(f"[{symbol}] Received {len(candles.get('data', []))} candles")

                direction, signal_type = analyze_signal(symbol, candles, config)

                if direction:
                    signals_found += 1
                    logger.info(f"✅ Signal detected for {symbol}: {direction.upper()} ({signal_type})")
                    trade_logger.info(f"SIGNAL | {symbol} | {direction.upper()} | {signal_type} | Price: TBD")
                    enter_trade(symbol, direction, signal_type)

            except Exception as e:
                errors_count += 1
                logger.error(f"❌ Error analyzing {symbol}: {str(e)}", exc_info=True)

        # Check open trades for exits
        try:
            check_and_close_trades()
        except Exception as e:
            logger.error(f"❌ Error checking trades: {str(e)}", exc_info=True)

        # Periodic position synchronization (only for live trading)
        if not PAPER_TRADING and position_sync.should_sync():
            logger.info("🔄 Performing periodic position sync...")
            position_sync.sync_positions_with_exchange()

        # Cycle summary with position info
        if not PAPER_TRADING:
            summary = position_sync.get_position_summary()
            logger.info(f"📊 Cycle #{cycle_count} complete - Signals: {signals_found}, Errors: {errors_count}")
            logger.info(f"   💰 Positions: {summary['total_positions']} | Unrealized P&L: ${summary['unrealized_pnl']:.2f}")
        else:
            logger.info(f"📊 Cycle #{cycle_count} complete - Signals: {signals_found}, Errors: {errors_count}, Paper trades: {len(open_trades)}")
        
        # Show portfolio report every 12 hours (every 48 cycles at 15min intervals)
        if cycle_count % 48 == 0:
            logger.info("📈 Generating portfolio performance report...")
            portfolio.print_performance_report()
        
        # Show margin usage report every 4 hours (every 16 cycles)
        if cycle_count % 16 == 0 and not PAPER_TRADING:
            logger.info("📊 Generating margin usage report...")
            try:
                from bot.exchange_okx import report_margin_usage
                report_margin_usage()
            except Exception as e:
                logger.error(f"❌ Error generating margin report: {e}")
        
        # Sleep between cycles (15 minutes = 900 seconds)
        logger.info("💤 Sleeping for 15 minutes...")
        time.sleep(900)

if __name__ == "__main__":
    # Validate configuration before starting
    if not validate_config():
        logger.error("❌ Configuration validation failed. Exiting.")
        sys.exit(1)
    
    try:
        run_strategy_loop()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
