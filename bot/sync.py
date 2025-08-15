import time
from bot.exchange_okx import get_open_positions
from bot.trade_executor import open_trades
from bot.logger import logger, trade_logger

class PositionSynchronizer:
    def __init__(self):
        self.last_sync = 0
        self.sync_interval = 300  # Sync every 5 minutes
        
    def sync_positions_with_exchange(self):
        """
        Synchronize local open_trades dict with actual exchange positions.
        This ensures the bot is aware of all positions even after restarts.
        """
        try:
            logger.info("🔄 Synchronizing positions with exchange...")
            
            # Get actual positions from exchange
            exchange_positions = get_open_positions()
            
            # Convert to dict keyed by symbol for easier comparison
            exchange_positions_dict = {pos["instId"]: pos for pos in exchange_positions}
            
            # Check for positions on exchange not in local tracking
            for symbol, exchange_pos in exchange_positions_dict.items():
                if symbol not in open_trades:
                    logger.warning(f"⚠️  Found untracked position on exchange: {symbol}")
                    
                    # Try to restore from persistent storage first
                    from bot.position_storage import position_storage
                    saved_position = position_storage.load_position(symbol)
                    
                    if saved_position and saved_position.get("stop_loss") and saved_position.get("take_profit"):
                        # Restore full position data including stop loss/take profit
                        open_trades[symbol] = saved_position
                        logger.info(f"✅ Restored position {symbol} with stop loss/take profit from storage")
                    else:
                        # No saved data - track as-is without risk management
                        open_trades[symbol] = {
                            "direction": "long" if float(exchange_pos["size"]) > 0 else "short",
                            "entry_price": float(exchange_pos["avgPx"]),
                            "size": abs(float(exchange_pos["size"])),
                            "stop_loss": None,  # Unknown
                            "take_profit": None,  # Unknown
                            "signal_type": "manual_or_restart",
                            "opened_at": time.time(),  # Approximate
                            "synced_from_exchange": True,
                            "paper_trade": False
                        }
                        logger.warning(f"⚠️  No saved risk management data for {symbol}")
                    
                    logger.info(f"✅ Added untracked position {symbol} to local tracking")
                    trade_logger.info(f"SYNC | {symbol} | FOUND_ON_EXCHANGE | Size: {exchange_pos['size']} | Avg: ${exchange_pos['avgPx']}")
            
            # Check for positions in local tracking not on exchange
            symbols_to_remove = []
            for symbol in open_trades.keys():
                if symbol not in exchange_positions_dict:
                    if not open_trades[symbol].get("paper_trade", False):
                        logger.warning(f"⚠️  Local position {symbol} not found on exchange - removing from tracking")
                        trade_logger.info(f"SYNC | {symbol} | NOT_ON_EXCHANGE | Removing from local tracking")
                        symbols_to_remove.append(symbol)
            
            # Remove stale positions
            for symbol in symbols_to_remove:
                open_trades.pop(symbol, None)
                
                # Remove from persistent storage
                from bot.position_storage import position_storage
                position_storage.remove_position(symbol)
            
            logger.info(f"✅ Position sync complete - Exchange: {len(exchange_positions)}, Local: {len(open_trades)}")
            self.last_sync = time.time()
            
        except Exception as e:
            logger.error(f"❌ Error syncing positions: {str(e)}")
    
    def should_sync(self):
        """Check if it's time to sync positions."""
        return time.time() - self.last_sync > self.sync_interval
    
    def force_sync(self):
        """Force immediate position synchronization."""
        self.sync_positions_with_exchange()
    
    def get_position_summary(self):
        """Get a summary of current positions."""
        try:
            exchange_positions = get_open_positions()
            
            summary = {
                "total_positions": len(exchange_positions),
                "unrealized_pnl": sum(float(pos.get("upl", 0)) for pos in exchange_positions),
                "positions": []
            }
            
            for pos in exchange_positions:
                summary["positions"].append({
                    "symbol": pos["instId"],
                    "side": pos["side"],
                    "size": float(pos["size"]),
                    "avg_price": float(pos["avgPx"]),
                    "unrealized_pnl": float(pos.get("upl", 0)),
                    "pnl_ratio": float(pos.get("uplRatio", 0)) * 100
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting position summary: {str(e)}")
            return {"total_positions": 0, "unrealized_pnl": 0, "positions": []}

# Global synchronizer instance
position_sync = PositionSynchronizer()