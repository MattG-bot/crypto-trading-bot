# Crypto Trading Bot - Live Trading Ready

A sophisticated cryptocurrency trading bot built for OKX exchange with comprehensive safety features, risk management, and portfolio tracking.

## 🚀 Features

- **Multi-Strategy Trading**: Memecoin, traditional, and momentum strategies
- **Comprehensive Safety**: Equity kill switch, position limits, consecutive loss protection
- **Real-time Monitoring**: Live position synchronization and P&L tracking
- **Paper Trading**: Test strategies without real money
- **Advanced Logging**: Detailed trade logs and performance reports
- **Risk Management**: ATR-based position sizing and 2R profit targets

## 📋 Prerequisites

- Python 3.8+
- OKX Exchange Account with API access
- Sufficient funds for trading (recommended minimum: $1000)

## 🛠️ Installation

1. **Clone and Setup**
   ```bash
   cd crypto-trading-bot
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API credentials and settings
   ```

3. **Required Environment Variables**
   ```bash
   # OKX API (get from OKX -> Profile -> API Management)
   OKX_API_KEY=your_api_key_here
   OKX_API_SECRET=your_api_secret_here  
   OKX_API_PASSPHRASE=your_passphrase_here
   
   # Trading Configuration
   TRADING_SYMBOLS=BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP
   PAPER_TRADING=true  # Set to 'false' for live trading
   ```

## ⚡ Quick Start

### Paper Trading (Recommended First)
```bash
# Ensure PAPER_TRADING=true in .env
python scripts/run_bot.py
```

### Live Trading (After Paper Testing)
```bash
# Set PAPER_TRADING=false in .env
# ⚠️ WARNING: This trades real money!
python scripts/run_bot.py
```

## 🛡️ Safety Features

### Built-in Protections
- **Equity Kill Switch**: Stops trading if account falls below threshold
- **Daily Loss Limit**: 5% maximum daily loss protection  
- **Position Limits**: Maximum concurrent positions (default: 5)
- **Consecutive Loss Protection**: Cooling-off after 3 consecutive losses
- **Position Size Validation**: Ensures trades within risk parameters

### Configuration (config.yaml)
```yaml
starting_equity: 10000
risk_per_trade_pct: 0.02  # 2% risk per trade
max_open_trades: 5
equity_kill_switch: 5000  # Stop if equity falls below this
```

## 📊 Monitoring & Logs

### Log Files (auto-created in `/logs`)
- `bot_YYYYMMDD.log`: Detailed bot operations
- `trades_YYYYMMDD.log`: Trade-specific events  
- `trades_history.json`: Complete trade history
- `daily_stats.json`: Daily performance statistics

### Performance Reports
- Automatic reports every 12 hours
- Portfolio P&L tracking
- Win/loss statistics
- Symbol performance breakdown

## 🔧 Configuration

### Trading Parameters
```yaml
# RSI Settings
rsi:
  period: 14
  long_threshold: 45
  short_threshold: 55

# Risk Management  
atr:
  period: 14
  stop_loss_multiplier: 2
  trailing_sl_multiplier: 1
```

### Supported Trading Pairs
- **Traditional**: BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP
- **Memecoins**: BONK-USDT-SWAP, PEPE-USDT-SWAP, PENGU-USDT-SWAP

## ⚠️ Important Warnings

### Before Live Trading
1. **Test Thoroughly**: Run paper trading for at least 1 week
2. **Start Small**: Use small position sizes initially
3. **Monitor Closely**: Watch the first few days carefully
4. **Have Funds**: Ensure sufficient margin for trades
5. **Understand Risks**: Cryptocurrency trading carries high risk

### Risk Disclosure
- Past performance doesn't guarantee future results
- You can lose money trading cryptocurrencies
- Only invest what you can afford to lose
- The bot is provided as-is with no guarantees

## 🔄 Operational Flow

1. **Startup**: Configuration validation and position sync
2. **Signal Detection**: Technical analysis every 60 minutes
3. **Trade Execution**: Safety checks → Position sizing → Order placement
4. **Risk Management**: Continuous stop-loss and take-profit monitoring
5. **Position Sync**: Regular synchronization with exchange
6. **Reporting**: Performance tracking and logging

## 🛠️ Troubleshooting

### Common Issues
- **API Errors**: Check credentials and permissions
- **No Signals**: Market conditions may not meet criteria
- **Position Sync Issues**: Manually close positions if needed
- **High CPU Usage**: Increase cycle time if needed

### Emergency Stop
- **Ctrl+C**: Graceful shutdown (recommended)
- **Kill Switch**: Automatic stop if losses exceed limits
- **Manual Override**: Close positions directly on OKX if needed

## 📈 Strategy Overview

### Signal Priority
1. **Memecoin Signals**: Bollinger Band breakouts with high volume
2. **Traditional Signals**: RSI + EMA + volume confirmation
3. **Momentum Signals**: EMA + MACD crossovers + RSI

### Risk Management
- **Position Sizing**: ATR-based with 2% account risk
- **Stop Loss**: 2x ATR distance
- **Take Profit**: 2:1 risk-reward ratio (2R)
- **Maximum Drawdown**: 5% daily limit

## 🆘 Support

For issues or questions:
1. Check logs in `/logs` directory
2. Review configuration in `.env` and `config.yaml`
3. Test in paper trading mode first
4. Ensure API permissions are correct

## 📜 License

This trading bot is for educational and personal use. Use at your own risk.

---

**⚡ Ready to start? Begin with paper trading to test everything works correctly!**