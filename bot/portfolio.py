import json
import os
from datetime import datetime, date
from typing import Dict, List
from bot.config import config
from bot.exchange_okx import get_account_equity
from bot.logger import logger

class PortfolioTracker:
    def __init__(self):
        self.starting_equity = config.get('starting_equity', 10000)
        self.trades_file = "logs/trades_history.json"
        self.daily_stats_file = "logs/daily_stats.json"
        
        # Initialize files if they don't exist
        self._initialize_files()
        
        # Load trade history
        self.trade_history = self._load_trade_history()
        self.daily_stats = self._load_daily_stats()
        
    def _initialize_files(self):
        """Create tracking files if they don't exist."""
        os.makedirs("logs", exist_ok=True)
        
        if not os.path.exists(self.trades_file):
            with open(self.trades_file, 'w') as f:
                json.dump([], f)
                
        if not os.path.exists(self.daily_stats_file):
            with open(self.daily_stats_file, 'w') as f:
                json.dump({}, f)
    
    def _load_trade_history(self) -> List[Dict]:
        """Load trade history from file."""
        try:
            with open(self.trades_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading trade history: {e}")
            return []
    
    def _save_trade_history(self):
        """Save trade history to file."""
        try:
            with open(self.trades_file, 'w') as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving trade history: {e}")
    
    def _load_daily_stats(self) -> Dict:
        """Load daily statistics from file."""
        try:
            with open(self.daily_stats_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading daily stats: {e}")
            return {}
    
    def _save_daily_stats(self):
        """Save daily statistics to file."""
        try:
            with open(self.daily_stats_file, 'w') as f:
                json.dump(self.daily_stats, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving daily stats: {e}")
    
    def record_trade(self, symbol: str, direction: str, entry_price: float, 
                    exit_price: float, size: float, exit_reason: str,
                    signal_type: str, duration_minutes: float):
        """Record a completed trade in the history."""
        
        # Calculate P&L
        if direction == "long":
            pnl_absolute = (exit_price - entry_price) * size
            pnl_percentage = ((exit_price - entry_price) / entry_price) * 100
        else:  # short
            pnl_absolute = (entry_price - exit_price) * size  
            pnl_percentage = ((entry_price - exit_price) / entry_price) * 100
        
        trade_record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl_absolute": round(pnl_absolute, 2),
            "pnl_percentage": round(pnl_percentage, 2),
            "exit_reason": exit_reason,
            "signal_type": signal_type,
            "duration_minutes": round(duration_minutes, 1),
            "is_winner": pnl_absolute > 0
        }
        
        self.trade_history.append(trade_record)
        self._save_trade_history()
        
        # Update daily statistics
        self._update_daily_stats(trade_record)
        
        logger.info(f"📝 Trade recorded: {symbol} | {direction.upper()} | P&L: ${pnl_absolute:.2f} ({pnl_percentage:.2f}%)")
        
        return trade_record
    
    def _update_daily_stats(self, trade_record: Dict):
        """Update daily statistics with new trade."""
        today = date.today().isoformat()
        
        if today not in self.daily_stats:
            self.daily_stats[today] = {
                "trades_count": 0,
                "winners": 0,
                "losers": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "symbols_traded": set()
            }
        
        stats = self.daily_stats[today]
        stats["trades_count"] += 1
        stats["total_pnl"] += trade_record["pnl_absolute"]
        stats["symbols_traded"].add(trade_record["symbol"])
        
        if trade_record["is_winner"]:
            stats["winners"] += 1
        else:
            stats["losers"] += 1
        
        # Calculate ratios
        if stats["trades_count"] > 0:
            stats["win_rate"] = (stats["winners"] / stats["trades_count"]) * 100
        
        # Calculate average win/loss
        wins = [t["pnl_absolute"] for t in self.trade_history if t["is_winner"] and t["timestamp"].startswith(today)]
        losses = [abs(t["pnl_absolute"]) for t in self.trade_history if not t["is_winner"] and t["timestamp"].startswith(today)]
        
        stats["avg_win"] = sum(wins) / len(wins) if wins else 0
        stats["avg_loss"] = sum(losses) / len(losses) if losses else 0
        
        # Calculate profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = sum(losses) if losses else 0
        stats["profit_factor"] = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0
        
        # Convert set to list for JSON serialization
        stats["symbols_traded"] = list(stats["symbols_traded"])
        
        self._save_daily_stats()
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio performance summary."""
        try:
            current_equity = get_account_equity()
            total_return = current_equity - self.starting_equity
            total_return_pct = (total_return / self.starting_equity) * 100 if self.starting_equity > 0 else 0
            
            # Calculate overall statistics
            if self.trade_history:
                total_trades = len(self.trade_history)
                winners = sum(1 for t in self.trade_history if t["is_winner"])
                win_rate = (winners / total_trades) * 100 if total_trades > 0 else 0
                
                total_pnl = sum(t["pnl_absolute"] for t in self.trade_history)
                avg_trade = total_pnl / total_trades if total_trades > 0 else 0
                
                wins = [t["pnl_absolute"] for t in self.trade_history if t["is_winner"]]
                losses = [abs(t["pnl_absolute"]) for t in self.trade_history if not t["is_winner"]]
                
                avg_win = sum(wins) / len(wins) if wins else 0
                avg_loss = sum(losses) / len(losses) if losses else 0
                
                profit_factor = sum(wins) / sum(losses) if losses else float('inf') if wins else 0
            else:
                total_trades = winners = win_rate = total_pnl = avg_trade = avg_win = avg_loss = profit_factor = 0
            
            return {
                "starting_equity": self.starting_equity,
                "current_equity": current_equity,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "total_trades": total_trades,
                "winners": winners,
                "losers": total_trades - winners,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "avg_trade": avg_trade,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": profit_factor
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting portfolio summary: {e}")
            return {"error": str(e)}
    
    def get_daily_performance(self, days: int = 7) -> Dict:
        """Get performance for the last N days."""
        from datetime import timedelta
        
        performance = {}
        today = date.today()
        
        for i in range(days):
            day = (today - timedelta(days=i)).isoformat()
            performance[day] = self.daily_stats.get(day, {
                "trades_count": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0
            })
        
        return performance
    
    def get_symbol_performance(self) -> Dict:
        """Get performance breakdown by symbol."""
        symbol_stats = {}
        
        for trade in self.trade_history:
            symbol = trade["symbol"]
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    "trades": 0,
                    "winners": 0,
                    "total_pnl": 0.0,
                    "win_rate": 0.0
                }
            
            stats = symbol_stats[symbol]
            stats["trades"] += 1
            stats["total_pnl"] += trade["pnl_absolute"]
            if trade["is_winner"]:
                stats["winners"] += 1
            
            stats["win_rate"] = (stats["winners"] / stats["trades"]) * 100
        
        return symbol_stats
    
    def print_performance_report(self):
        """Print a detailed performance report."""
        summary = self.get_portfolio_summary()
        
        if "error" in summary:
            logger.error(f"❌ Cannot generate performance report: {summary['error']}")
            return
        
        logger.info("📊 PORTFOLIO PERFORMANCE REPORT")
        logger.info("=" * 50)
        logger.info(f"💰 Starting Equity: ${summary['starting_equity']:,.2f}")
        logger.info(f"💰 Current Equity:  ${summary['current_equity']:,.2f}")
        logger.info(f"📈 Total Return:    ${summary['total_return']:,.2f} ({summary['total_return_pct']:+.2f}%)")
        logger.info(f"🎯 Total Trades:    {summary['total_trades']}")
        logger.info(f"✅ Winners:         {summary['winners']} ({summary['win_rate']:.1f}%)")
        logger.info(f"❌ Losers:          {summary['losers']}")
        logger.info(f"💵 Avg Trade:       ${summary['avg_trade']:,.2f}")
        logger.info(f"🟢 Avg Win:         ${summary['avg_win']:,.2f}")
        logger.info(f"🔴 Avg Loss:        ${summary['avg_loss']:,.2f}")
        logger.info(f"⚡ Profit Factor:   {summary['profit_factor']:.2f}")
        logger.info("=" * 50)

# Global portfolio tracker instance
portfolio = PortfolioTracker()