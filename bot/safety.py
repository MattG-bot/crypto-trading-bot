import time
from bot.config import config
from bot.exchange_okx import get_account_equity
from bot.logger import logger, trade_logger

class SafetyManager:
    def __init__(self):
        self.starting_equity = config.get('starting_equity', 10000)
        self.equity_kill_switch_pct = config.get('equity_kill_switch_pct', 0.5)  # 50% kill switch
        self.max_open_trades = config.get('max_open_trades', 5)
        self.risk_per_trade_pct = config.get('risk_per_trade_pct', 0.02)
        
        # Track safety statistics - percentage-based limits
        self.daily_loss_limit_pct = config.get('daily_loss_limit_pct', 0.05)  # 5% daily loss limit
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        self.last_equity_check = time.time()
        self.equity_check_interval = 300  # Check every 5 minutes
        
        # Emergency stop flag
        self.emergency_stop = False
        
        kill_switch_amount = self.starting_equity * self.equity_kill_switch_pct
        daily_loss_amount = self.starting_equity * self.daily_loss_limit_pct
        logger.info(f"🛡️  Safety Manager initialized - Kill switch: {self.equity_kill_switch_pct*100}% (${kill_switch_amount:.0f}) | Daily limit: {self.daily_loss_limit_pct*100}% (${daily_loss_amount:.0f})")
        
    def check_equity_kill_switch(self):
        """Check if account equity has fallen below kill switch threshold."""
        try:
            current_equity = get_account_equity()
            
            # Calculate percentage-based thresholds
            equity_kill_threshold = self.starting_equity * self.equity_kill_switch_pct
            daily_loss_threshold = self.starting_equity * self.daily_loss_limit_pct
            
            # Check equity kill switch (percentage-based)
            if current_equity <= equity_kill_threshold:
                self.emergency_stop = True
                logger.critical(f"🚨 EQUITY KILL SWITCH TRIGGERED! Current: ${current_equity:.2f} <= {self.equity_kill_switch_pct*100}% threshold (${equity_kill_threshold:.2f})")
                trade_logger.critical(f"KILL_SWITCH | EQUITY | ${current_equity:.2f} <= ${equity_kill_threshold:.2f}")
                return False
                
            # Check daily loss limit (percentage-based)
            daily_loss = self.starting_equity - current_equity
            if daily_loss >= daily_loss_threshold:
                self.emergency_stop = True
                logger.critical(f"🚨 DAILY LOSS LIMIT EXCEEDED! Loss: ${daily_loss:.2f} >= {self.daily_loss_limit_pct*100}% limit (${daily_loss_threshold:.2f})")
                trade_logger.critical(f"KILL_SWITCH | DAILY_LOSS | ${daily_loss:.2f} >= ${daily_loss_threshold:.2f}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking equity kill switch: {e}")
            return True  # Fail safe - don't stop on error
    
    def check_position_limits(self, open_trades):
        """Check if we're at maximum position limits."""
        if len(open_trades) >= self.max_open_trades:
            logger.warning(f"⚠️  Maximum open trades reached: {len(open_trades)}/{self.max_open_trades}")
            return False
        return True
    
    def check_consecutive_losses(self, trade_result):
        """Track consecutive losses and implement cooling off period."""
        if trade_result == "loss":
            self.consecutive_losses += 1
            logger.warning(f"📉 Consecutive losses: {self.consecutive_losses}")
            
            if self.consecutive_losses >= self.max_consecutive_losses:
                logger.warning(f"🔄 Cooling off period activated after {self.consecutive_losses} losses")
                return False
        else:
            self.consecutive_losses = 0
            
        return True
    
    def validate_trade_size(self, symbol, trade_size, current_price):
        """Validate that trade size is within perpetual futures margin limits."""
        try:
            from bot.exchange_okx import get_account_margin_info
            margin_info = get_account_margin_info()
            
            if not margin_info:
                logger.warning(f"⚠️  Could not get margin info for {symbol} validation, allowing trade")
                return True
                
            available_margin = margin_info['availBal']
            trade_value = trade_size * current_price
            
            # For perpetual futures: validate based on margin usage, not notional value
            # Estimate margin requirement based on typical leverage for each asset
            leverage_estimates = {
                'BTC-USDT-SWAP': 20,   'ETH-USDT-SWAP': 20,   'SOL-USDT-SWAP': 15,
                'XRP-USDT-SWAP': 10,   'LTC-USDT-SWAP': 10,   'ADA-USDT-SWAP': 10,
                'AVAX-USDT-SWAP': 10,  'LINK-USDT-SWAP': 10,  'NEAR-USDT-SWAP': 10
            }
            
            estimated_leverage = leverage_estimates.get(symbol, 10)
            estimated_margin_needed = trade_value / estimated_leverage
            
            # Don't allow more than 25% of available margin per single position
            max_margin_per_position = available_margin * 0.25
            
            if estimated_margin_needed > max_margin_per_position:
                logger.warning(f"⚠️  Margin requirement too high for {symbol}: ${estimated_margin_needed:.2f} > ${max_margin_per_position:.2f} (25% of available)")
                return False
            
            # Check minimum notional value for perpetual futures (typically $10+ for crypto)
            min_notional = 10
            if trade_value < min_notional:
                logger.warning(f"⚠️  Position too small for {symbol}: ${trade_value:.2f} (min: ${min_notional})")
                return False
            
            logger.info(f"✅ {symbol} margin validation passed: ${estimated_margin_needed:.2f} margin needed, ${available_margin:.2f} available")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validating trade size for {symbol}: {e}")
            return False
    
    def reset_emergency_stop(self):
        """Reset emergency stop flag manually."""
        self.emergency_stop = False
        logger.info("✅ Emergency stop has been reset manually")
    
    def update_starting_equity(self, new_equity):
        """Update starting equity baseline (e.g., daily reset or after major profits)."""
        old_equity = self.starting_equity
        self.starting_equity = new_equity
        
        # Recalculate thresholds
        new_kill_threshold = new_equity * self.equity_kill_switch_pct
        new_daily_limit = new_equity * self.daily_loss_limit_pct
        
        logger.info(f"📊 Starting equity updated: ${old_equity:.0f} → ${new_equity:.0f}")
        logger.info(f"🛡️  New kill switch: ${new_kill_threshold:.0f} | New daily limit: ${new_daily_limit:.0f}")
    
    def should_allow_trading(self, open_trades):
        """Master safety check - returns True if trading should continue."""
        current_time = time.time()
        
        # Check emergency stop
        if self.emergency_stop:
            logger.warning("🚨 Emergency stop is active - no new trades allowed")
            return False
        
        # Periodic equity check
        if current_time - self.last_equity_check > self.equity_check_interval:
            if not self.check_equity_kill_switch():
                return False
            self.last_equity_check = current_time
        
        # Check position limits
        if not self.check_position_limits(open_trades):
            return False
            
        return True
    
    def get_safe_position_size(self, symbol, entry_price, stop_loss):
        """Calculate position size based on risk management rules."""
        try:
            current_equity = get_account_equity()
            risk_amount = current_equity * self.risk_per_trade_pct
            price_diff = abs(entry_price - stop_loss)
            
            if price_diff == 0:
                logger.error(f"❌ Invalid stop loss for {symbol} - no price difference")
                return 0
            
            # For futures/swaps: position size = risk_amount / (price_diff / entry_price)
            # This gives us the contract size where the price movement equals our risk
            position_size = risk_amount / price_diff
            
            # Cap position size to reasonable limits for futures
            max_notional = risk_amount * 10  # Max 10x of risk amount as notional
            max_position_size = max_notional / entry_price
            
            if position_size > max_position_size:
                position_size = max_position_size
                logger.warning(f"⚠️  Position size capped for {symbol}: {position_size:.4f} contracts")
            
            # Validate the calculated size
            if self.validate_trade_size(symbol, position_size, entry_price):
                return position_size
            else:
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error calculating safe position size for {symbol}: {e}")
            return 0

# Global safety manager instance
safety_manager = SafetyManager()