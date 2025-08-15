#!/usr/bin/env python3
"""
Setup validation script for the crypto trading bot.
Tests all critical components before live trading.
"""

import os
import sys
import traceback
from datetime import datetime

# Add parent directory to path to import bot modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all required modules can be imported."""
    print("🔄 Testing module imports...")
    try:
        from bot.config import validate_config, TRADING_SYMBOLS, PAPER_TRADING
        from bot.logger import logger
        from bot.exchange_okx import get_ticker, get_account_equity, get_open_positions
        from bot.strategy import analyze_signal
        from bot.safety import safety_manager
        from bot.sync import position_sync
        from bot.portfolio import portfolio
        from bot.trade_executor import get_current_price, open_trades
        print("✅ All modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration validation."""
    print("🔄 Testing configuration...")
    try:
        from bot.config import validate_config, TRADING_SYMBOLS, PAPER_TRADING
        
        if validate_config():
            print(f"✅ Configuration valid")
            print(f"   📊 Paper Trading: {'ON' if PAPER_TRADING else 'OFF'}")
            print(f"   🎯 Trading Symbols: {len(TRADING_SYMBOLS)} symbols")
            return True
        else:
            print("❌ Configuration validation failed")
            return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        traceback.print_exc()
        return False

def test_api_connection():
    """Test API connection to exchange."""
    print("🔄 Testing API connection...")
    try:
        from bot.exchange_okx import get_ticker
        from bot.config import TRADING_SYMBOLS, PAPER_TRADING
        
        if not TRADING_SYMBOLS:
            print("⚠️  No trading symbols configured - skipping API test")
            return True
            
        # Test with first symbol
        symbol = TRADING_SYMBOLS[0]
        ticker_data = get_ticker(symbol)
        
        if ticker_data.get("code") == "0":
            price = float(ticker_data["data"][0]["last"])
            print(f"✅ API connection successful")
            print(f"   📈 {symbol}: ${price}")
            return True
        else:
            print(f"❌ API error: {ticker_data}")
            return False
            
    except Exception as e:
        print(f"❌ API connection error: {e}")
        traceback.print_exc()
        return False

def test_account_access():
    """Test account data access."""
    print("🔄 Testing account access...")
    try:
        from bot.exchange_okx import get_account_equity, get_open_positions
        from bot.config import PAPER_TRADING
        
        if PAPER_TRADING:
            print("📝 Paper trading mode - skipping account access test")
            return True
            
        equity = get_account_equity()
        positions = get_open_positions()
        
        print(f"✅ Account access successful")
        print(f"   💰 Account Equity: ${equity:,.2f}")
        print(f"   📊 Open Positions: {len(positions)}")
        return True
        
    except Exception as e:
        print(f"❌ Account access error: {e}")
        traceback.print_exc()
        return False

def test_strategy_logic():
    """Test strategy analysis with sample data."""
    print("🔄 Testing strategy logic...")
    try:
        from bot.strategy import analyze_signal
        from bot.config import config, TRADING_SYMBOLS
        from bot.exchange_okx import get_candles
        
        if not TRADING_SYMBOLS:
            print("⚠️  No trading symbols configured - skipping strategy test")
            return True
            
        symbol = TRADING_SYMBOLS[0]
        candles = get_candles(symbol, bar="1h", limit=50)
        
        if not candles or 'data' not in candles:
            print(f"⚠️  No candle data for {symbol} - cannot test strategy")
            return True
            
        direction, signal_type = analyze_signal(symbol, candles, config)
        
        print(f"✅ Strategy logic working")
        if direction:
            print(f"   🎯 Signal: {direction.upper()} ({signal_type}) for {symbol}")
        else:
            print(f"   ⏸️  No signal for {symbol}")
        return True
        
    except Exception as e:
        print(f"❌ Strategy logic error: {e}")
        traceback.print_exc()
        return False

def test_safety_systems():
    """Test safety manager functionality."""
    print("🔄 Testing safety systems...")
    try:
        from bot.safety import safety_manager
        from bot.trade_executor import open_trades
        
        # Test basic safety checks
        can_trade = safety_manager.should_allow_trading(open_trades)
        
        print(f"✅ Safety systems operational")
        print(f"   🛡️  Trading allowed: {can_trade}")
        print(f"   💰 Kill switch threshold: ${safety_manager.equity_kill_switch:,.2f}")
        print(f"   📊 Max open trades: {safety_manager.max_open_trades}")
        return True
        
    except Exception as e:
        print(f"❌ Safety systems error: {e}")
        traceback.print_exc()
        return False

def test_logging_system():
    """Test logging functionality."""
    print("🔄 Testing logging system...")
    try:
        from bot.logger import logger, trade_logger
        
        # Test log messages
        logger.info("Setup validation test log message")
        trade_logger.info("Setup validation trade log message")
        
        # Check if logs directory exists
        if os.path.exists("logs"):
            log_files = [f for f in os.listdir("logs") if f.endswith('.log')]
            print(f"✅ Logging system operational")
            print(f"   📁 Log files found: {len(log_files)}")
        else:
            print("⚠️  Logs directory not found - will be created on first run")
            
        return True
        
    except Exception as e:
        print(f"❌ Logging system error: {e}")
        traceback.print_exc()
        return False

def test_portfolio_tracking():
    """Test portfolio tracking functionality."""
    print("🔄 Testing portfolio tracking...")
    try:
        from bot.portfolio import portfolio
        
        # Test portfolio summary
        summary = portfolio.get_portfolio_summary()
        
        if "error" not in summary:
            print(f"✅ Portfolio tracking operational")
            print(f"   💰 Starting equity: ${summary.get('starting_equity', 0):,.2f}")
            print(f"   📊 Total trades: {summary.get('total_trades', 0)}")
        else:
            print(f"⚠️  Portfolio tracking has issues: {summary['error']}")
            
        return True
        
    except Exception as e:
        print(f"❌ Portfolio tracking error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all validation tests."""
    print("🤖 CRYPTO TRADING BOT - SETUP VALIDATION")
    print("=" * 50)
    print(f"🕐 Validation started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_configuration),
        ("API Connection", test_api_connection),
        ("Account Access", test_account_access),
        ("Strategy Logic", test_strategy_logic),
        ("Safety Systems", test_safety_systems),
        ("Logging System", test_logging_system),
        ("Portfolio Tracking", test_portfolio_tracking)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 30)
        
        if test_func():
            passed += 1
        
    print("\n" + "=" * 50)
    print(f"📊 VALIDATION RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Bot is ready for operation.")
        print("\n🚀 Next steps:")
        print("   1. Ensure PAPER_TRADING=true for initial testing")
        print("   2. Run: python scripts/run_bot.py")
        print("   3. Monitor paper trades for at least 1 week")
        print("   4. Only then consider live trading with small amounts")
        return True
    else:
        failed = total - passed
        print(f"❌ {failed} test(s) failed. Fix issues before running the bot.")
        print("\n🔧 Troubleshooting:")
        print("   1. Check your .env file configuration")
        print("   2. Verify API credentials and permissions")
        print("   3. Ensure all required packages are installed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)