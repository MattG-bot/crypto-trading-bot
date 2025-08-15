#!/usr/bin/env python3
# Reset emergency stop flag

from bot.safety import safety_manager
from bot.logger import logger

def reset_emergency_stop():
    """Reset the emergency stop flag."""
    logger.info("🔄 Resetting emergency stop...")
    safety_manager.reset_emergency_stop()
    logger.info("✅ Emergency stop reset complete")

if __name__ == "__main__":
    reset_emergency_stop()