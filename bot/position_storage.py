import json
import os
from typing import Dict, Any
from bot.logger import logger

class PositionStorage:
    def __init__(self):
        self.positions_file = "logs/active_positions.json"
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create positions file if it doesn't exist."""
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(self.positions_file):
            with open(self.positions_file, 'w') as f:
                json.dump({}, f)
    
    def save_position(self, symbol: str, position_data: Dict[str, Any]):
        """Save position data to persistent storage."""
        try:
            positions = self.load_all_positions()
            positions[symbol] = position_data
            
            with open(self.positions_file, 'w') as f:
                json.dump(positions, f, indent=2)
                
            logger.debug(f"💾 Saved position data for {symbol}")
        except Exception as e:
            logger.error(f"❌ Error saving position {symbol}: {e}")
    
    def load_position(self, symbol: str) -> Dict[str, Any]:
        """Load position data for a specific symbol."""
        try:
            positions = self.load_all_positions()
            return positions.get(symbol, {})
        except Exception as e:
            logger.error(f"❌ Error loading position {symbol}: {e}")
            return {}
    
    def load_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load all saved positions."""
        try:
            with open(self.positions_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Error loading positions: {e}")
            return {}
    
    def remove_position(self, symbol: str):
        """Remove position from storage when closed."""
        try:
            positions = self.load_all_positions()
            if symbol in positions:
                del positions[symbol]
                
                with open(self.positions_file, 'w') as f:
                    json.dump(positions, f, indent=2)
                    
                logger.debug(f"🗑️ Removed position data for {symbol}")
        except Exception as e:
            logger.error(f"❌ Error removing position {symbol}: {e}")
    
    def clear_all_positions(self):
        """Clear all stored positions (useful for testing)."""
        try:
            with open(self.positions_file, 'w') as f:
                json.dump({}, f)
            logger.info("🧹 Cleared all stored positions")
        except Exception as e:
            logger.error(f"❌ Error clearing positions: {e}")

# Global instance
position_storage = PositionStorage()