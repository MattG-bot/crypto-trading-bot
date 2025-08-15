# bot/config.py

import os
import yaml
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Load config.yaml
with open("config.yaml", "r") as f:
    yaml_config = yaml.safe_load(f)

# === API Credentials ===
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE")

# === Trading Settings ===
OKX_ACCOUNT_TYPE = os.getenv("OKX_ACCOUNT_TYPE", "5")  # 5 = Perps
OKX_MARGIN_MODE = os.getenv("OKX_MARGIN_MODE", "cross")
OKX_POSITION_SIDE = os.getenv("OKX_POSITION_SIDE", "long_short")
TRADING_SYMBOLS = [s.strip() for s in os.getenv("TRADING_SYMBOLS", "").split(",") if s.strip()]

# === Strategy Parameters ===
config = yaml_config  # Expose entire YAML config

# === Configuration Validation ===
def validate_config():
    """Validate that required configuration is present."""
    errors = []
    
    if not OKX_API_KEY:
        errors.append("OKX_API_KEY is required")
    if not OKX_API_SECRET:
        errors.append("OKX_API_SECRET is required") 
    if not OKX_API_PASSPHRASE:
        errors.append("OKX_API_PASSPHRASE is required")
    if not TRADING_SYMBOLS:
        errors.append("TRADING_SYMBOLS is required (comma-separated list)")
        
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"   - {error}")
        print("\n💡 Please check your .env file and ensure all required variables are set.")
        print("   Use .env.example as a template.")
        return False
        
    print("✅ Configuration validated successfully")
    return True

# === Additional Config ===
PAPER_TRADING = os.getenv("PAPER_TRADING", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
