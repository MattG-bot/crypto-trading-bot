import logging
import sys
from datetime import datetime
import os

def setup_logger():
    """Setup structured logging for the trading bot."""
    
    # Get log level from environment, default to INFO
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("crypto_bot")
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-5s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.FileHandler(f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    
    # Separate handler for trades
    trade_handler = logging.FileHandler(f"logs/trades_{datetime.now().strftime('%Y%m%d')}.log")
    trade_handler.setFormatter(detailed_formatter)
    trade_handler.setLevel(logging.INFO)
    
    # Create trade logger
    trade_logger = logging.getLogger("crypto_bot.trades")
    trade_logger.addHandler(trade_handler)
    trade_logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logger()
trade_logger = logging.getLogger("crypto_bot.trades")