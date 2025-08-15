# bot/position_migration.py

import time
from bot.risk import calculate_profit_levels
from bot.logger import logger

def migrate_position_to_staged_format(position_data):
    """
    Migrate old position format to new staged profit taking format.
    Returns updated position data.
    """
    # Check if already in new format
    if "profit_levels" in position_data and "profits_taken" in position_data:
        return position_data
    
    logger.info(f"🔄 Migrating position to staged profit format")
    
    # Extract existing data
    entry_price = position_data.get("entry_price")
    stop_loss = position_data.get("stop_loss")
    direction = position_data.get("direction")
    size = position_data.get("size")
    
    if not all([entry_price, stop_loss, direction, size]):
        logger.warning("⚠️  Missing required data for migration, keeping old format")
        return position_data
    
    # Calculate profit levels
    profit_levels = calculate_profit_levels(entry_price, stop_loss, direction)
    
    # Update position with new format
    position_data.update({
        "original_size": size,  # Track original size
        "profit_levels": profit_levels,
        "profits_taken": {  # Track which profit levels have been hit
            "1R": False,
            "2R": False, 
            "3R": False,
            "4R": False
        },
        "high_water_mark": entry_price,  # Initialize to entry price
        "trailing_stop_active": False,
        "atr": position_data.get("atr", 50.0),  # Estimate ATR if missing
        "take_profit": profit_levels["2R"]  # Backward compatibility
    })
    
    logger.info(f"✅ Position migrated - Profit levels: 1R=${profit_levels['1R']}, 2R=${profit_levels['2R']}, 3R=${profit_levels['3R']}, 4R=${profit_levels['4R']}")
    
    return position_data

def migrate_all_positions(open_trades):
    """
    Migrate all positions in open_trades to new format.
    """
    migrated_count = 0
    
    for symbol, position in open_trades.items():
        old_format = "profit_levels" not in position
        migrated_position = migrate_position_to_staged_format(position)
        open_trades[symbol] = migrated_position
        
        if old_format:
            migrated_count += 1
            
            # Update persistent storage
            try:
                from bot.position_storage import position_storage
                position_storage.save_position(symbol, migrated_position)
            except Exception as e:
                logger.error(f"❌ Error saving migrated position {symbol}: {e}")
    
    if migrated_count > 0:
        logger.info(f"🔄 Migrated {migrated_count} positions to staged profit format")
    
    return open_trades