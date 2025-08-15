#!/bin/bash

# Force correct API credentials from .env file
export OKX_API_KEY="1e501e98-ebab-41ba-b0ab-3f765b1d516e"
export OKX_API_SECRET="6331D6A929E4E87D5793C8291C1BF4AA"  
export OKX_API_PASSPHRASE="Bonk_Pengy67"
export OKX_ACCOUNT_TYPE="5"
export OKX_MARGIN_MODE="cross"
export OKX_POSITION_SIDE="long_short"

# Set Python path and run bot
export PYTHONPATH="/Users/mattgambles/crypto-trading-bot/crypto-trading-bot"

echo "Starting bot with correct API credentials..."
echo "API Key: ${OKX_API_KEY:0:8}..."

cd /Users/mattgambles/crypto-trading-bot/crypto-trading-bot
python3 scripts/run_bot.py