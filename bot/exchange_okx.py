# bot/exchange_okx.py

import json
import time
import uuid
import hmac
import hashlib
import requests
from datetime import datetime
from bot.config import OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE, OKX_ACCOUNT_TYPE, OKX_MARGIN_MODE

BASE_URL = "https://www.okx.com"

def _get_timestamp():
    return datetime.utcnow().isoformat("T", "milliseconds") + "Z"

def _sign(message, secret):
    import base64
    return base64.b64encode(hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()).decode()

def _headers(method, endpoint, body=""):
    timestamp = _get_timestamp()
    message = f"{timestamp}{method.upper()}{endpoint}{body}"
    signature = _sign(message, OKX_API_SECRET)

    print(f"Timestamp: {timestamp}")
    print(f"Message to sign: {message}")
    print(f"Signature: {signature}")

    return {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_API_PASSPHRASE,
        "Content-Type": "application/json"
    }


def get_candles(symbol, bar="1h", limit=100):
    endpoint = f"/api/v5/market/candles?instId={symbol}&bar={bar}&limit={limit}"
    url = BASE_URL + endpoint
    resp = requests.get(url, headers=_headers("GET", endpoint))
    data = resp.json()

    print(f"[{symbol}] candles received: {len(data.get('data', []))}")

    return data




# === GET Ticker ===
def get_ticker(symbol):
    endpoint = f"/api/v5/market/ticker?instId={symbol}"
    url = BASE_URL + endpoint
    resp = requests.get(url, headers=_headers("GET", endpoint))
    return resp.json()

# === GET Balance ===
def get_account_equity():
    from bot.config import PAPER_TRADING, config
    
    # For paper trading, return configured starting equity
    if PAPER_TRADING:
        return config.get('starting_equity', 10000)
    
    # For live trading, fetch real account data
    endpoint = f"/api/v5/account/balance"
    url = BASE_URL + endpoint
    resp = requests.get(url, headers=_headers("GET", endpoint))
    print(f"Raw response status: {resp.status_code}")
    print(f"Raw response text: {resp.text}")
    data = resp.json()

    usdt_balance = next((item for item in data.get('data', [{}])[0].get('details', []) if item.get('ccy') == 'USDT'), None)
    return float(usdt_balance['eq']) if usdt_balance else 0.0

def get_account_margin_info():
    """
    Get detailed margin information including used and available margin.
    Returns dict with totalEq, availBal, ordFrozen, etc.
    """
    from bot.config import PAPER_TRADING, config
    
    # For paper trading, simulate margin data
    if PAPER_TRADING:
        starting_equity = config.get('starting_equity', 10000)
        return {
            'totalEq': starting_equity,
            'availBal': starting_equity * 0.8,  # Simulate 80% available
            'ordFrozen': starting_equity * 0.2,  # Simulate 20% used
            'marginRatio': '0.15'
        }
    
    # For live trading, fetch real margin data
    endpoint = f"/api/v5/account/balance"
    url = BASE_URL + endpoint
    resp = requests.get(url, headers=_headers("GET", endpoint))
    data = resp.json()
    
    if data.get("code") != "0":
        print(f"Error fetching margin info: {data.get('msg', 'Unknown error')}")
        return None
        
    account_data = data.get('data', [{}])[0]
    usdt_detail = next((item for item in account_data.get('details', []) if item.get('ccy') == 'USDT'), None)
    
    if not usdt_detail:
        return None
        
    return {
        'totalEq': float(account_data.get('totalEq', 0)),  # Total equity
        'availBal': float(usdt_detail.get('availBal', 0)),  # Available balance for new orders
        'cashBal': float(usdt_detail.get('cashBal', 0)),    # Cash balance
        'ordFrozen': float(usdt_detail.get('ordFrozen', 0)), # Frozen for orders
        'marginRatio': account_data.get('mgnRatio', '0'),   # Margin ratio
        'used_margin': float(usdt_detail.get('cashBal', 0)) - float(usdt_detail.get('availBal', 0))  # Calculate used margin
    }


def get_valid_lot_size(symbol, size):
    """
    Round size to valid lot size for each instrument.
    Different tokens have different minimum lot size requirements.
    """
    # Define lot sizes for different instruments (based on OKX specifications)
    lot_sizes = {
        'BTC-USDT-SWAP': 0.01,     # Tick size: 0.1
        'ETH-USDT-SWAP': 0.01,     # Tick size: 0.01
        'SOL-USDT-SWAP': 0.1,      # Tick size: 0.01
        'XRP-USDT-SWAP': 0.1,      # Tick size: 0.0001
        'LTC-USDT-SWAP': 1.0,      # Tick size: 0.01 - but lot size might be 1.0
        'ADA-USDT-SWAP': 1.0,      # Tick size: 0.0001
        'AVAX-USDT-SWAP': 0.1,     # Tick size: 0.001
        'LINK-USDT-SWAP': 0.1,     # Tick size: 0.001
        'NEAR-USDT-SWAP': 0.1,     # Tick size: 0.001
        
        # Memecoins - very small lot sizes to stay under OKX limits
        'BONK-USDT-SWAP': 10,
        'PEPE-USDT-SWAP': 100, 
        'PENGU-USDT-SWAP': 1,
        
        # Default for any other symbols
        'DEFAULT': 0.1
    }
    
    lot_size = lot_sizes.get(symbol, lot_sizes['DEFAULT'])
    
    # Round to nearest valid lot size with proper precision
    lots = round(size / lot_size)
    rounded_size = lots * lot_size
    
    # Ensure minimum size is at least one lot
    if rounded_size < lot_size:
        rounded_size = lot_size
    
    # Fix floating point precision issues
    if lot_size >= 1.0:
        # For lot sizes >= 1, round to integers
        rounded_size = round(rounded_size)
    else:
        # For decimal lot sizes, round to appropriate decimal places
        decimal_places = len(str(lot_size).split('.')[-1])
        rounded_size = round(rounded_size, decimal_places)
        
    return rounded_size

# === Place Market Order ===
def get_real_time_margin_requirement(symbol, size, price):
    """
    Get real-time margin requirement for a proposed position from OKX.
    This uses OKX's actual calculation including fees and buffers.
    """
    try:
        # Use OKX's position estimation API to get accurate margin requirements
        endpoint = "/api/v5/account/position-risk"
        url = BASE_URL + endpoint
        
        params = {
            "instId": symbol,
            "sz": str(size),
            "px": str(price),
            "side": "buy"  # For estimation purposes
        }
        
        resp = requests.get(url, headers=_headers("GET", endpoint), params=params)
        data = resp.json()
        
        if data.get("code") == "0" and data.get("data"):
            position_risk = data["data"][0]
            # Extract actual margin requirement from OKX
            margin_required = float(position_risk.get("imr", 0))  # Initial margin requirement
            
            print(f"🎯 OKX REAL-TIME MARGIN for {symbol}:")
            print(f"   Size: {size} contracts")
            print(f"   Price: ${price}")
            print(f"   OKX Margin Required: ${margin_required:.2f}")
            
            return margin_required
        else:
            print(f"⚠️ Could not get OKX margin requirement for {symbol}: {data.get('msg', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting real-time margin for {symbol}: {e}")
        return None

def validate_margin_before_order(symbol, size, price):
    """
    Perform real-time margin validation immediately before order placement.
    Returns True if sufficient margin, False otherwise.
    """
    try:
        # Get current account margin info
        margin_info = get_account_margin_info()
        if not margin_info:
            print(f"❌ Cannot validate margin - failed to get account info")
            return False
            
        current_available = margin_info['availBal']
        
        # Get real-time margin requirement from OKX
        required_margin = get_real_time_margin_requirement(symbol, size, price)
        if required_margin is None:
            # Fallback to simplified calculation if OKX API fails
            notional_value = size * price
            required_margin = notional_value / 10  # Assume 10x leverage
            print(f"⚠️ Using fallback margin calculation: ${required_margin:.2f}")
        
        # Add 5% buffer for fees and market movement
        margin_with_buffer = required_margin * 1.05
        
        print(f"🔍 REAL-TIME MARGIN CHECK for {symbol}:")
        print(f"   Required (with buffer): ${margin_with_buffer:.2f}")
        print(f"   Available: ${current_available:.2f}")
        print(f"   Utilization: {(margin_with_buffer/current_available)*100:.1f}%")
        
        if margin_with_buffer <= current_available:
            print(f"✅ Margin validation PASSED")
            return True
        else:
            print(f"❌ Margin validation FAILED - insufficient margin")
            return False
            
    except Exception as e:
        print(f"❌ Error validating margin for {symbol}: {e}")
        return False

def place_order(symbol, side, size, reduce_only=False):
    endpoint = "/api/v5/trade/order"
    url = BASE_URL + endpoint
    
    # For reduce_only orders (closing positions), posSide should match the existing position
    # For opening orders, posSide should match the side direction
    if reduce_only:
        # When closing: if selling, we're closing a long position (posSide: long)
        # When closing: if buying, we're closing a short position (posSide: short)
        pos_side = "long" if side == "sell" else "short"
    else:
        # When opening: side and posSide match
        pos_side = "long" if side == "buy" else "short"
    
    # Use proper calculated size with lot adjustment
    adjusted_size = get_valid_lot_size(symbol, size)
    test_size = str(adjusted_size)
    
    # Get current price for margin validation
    ticker_data = get_ticker(symbol)
    if ticker_data.get("code") == "0" and ticker_data.get("data"):
        current_price = float(ticker_data["data"][0]["last"])
    else:
        print(f"⚠️ Could not get current price for {symbol}, using size-based estimate")
        current_price = 1.0  # Fallback
    
    # Perform real-time margin validation before placing order
    if not reduce_only:  # Only validate for opening positions
        if not validate_margin_before_order(symbol, adjusted_size, current_price):
            return {
                "code": "margin_validation_failed", 
                "msg": "Real-time margin validation failed - insufficient margin",
                "data": []
            }
    
    body = {
        "instId": symbol,
        "tdMode": OKX_MARGIN_MODE,
        "side": side,
        "ordType": "market", 
        "sz": test_size,
        "posSide": pos_side
    }
    
    # Only add reduceOnly if it's True (for closing positions)
    if reduce_only:
        body["reduceOnly"] = True
    
    # Debug logging - print exact order being sent
    print(f"🔍 DEBUG ORDER for {symbol}:")
    print(f"   Order Body: {body}")
    print(f"   Size: {test_size} (lot adjusted from {size:.4f})")
    
    body_json = json.dumps(body)
    headers = _headers("POST", endpoint, body_json)
    resp = requests.post(url, headers=headers, data=body_json)
    
    # Debug response
    response_data = resp.json()
    if response_data.get("code") != "0":
        print(f"❌ OKX Order Failed: {response_data}")
    
    return response_data
def get_open_positions():
    """
    Fetch open positions from OKX exchange with detailed margin information.
    Returns list of position dictionaries with actual margin usage.
    """
    endpoint = "/api/v5/account/positions"
    url = BASE_URL + endpoint
    
    try:
        resp = requests.get(url, headers=_headers("GET", endpoint))
        data = resp.json()
        
        if data.get("code") != "0":
            print(f"Error fetching positions: {data.get('msg', 'Unknown error')}")
            return []
            
        positions = []
        for pos in data.get("data", []):
            if float(pos.get("pos", 0)) != 0:  # Only non-zero positions
                size = float(pos.get("pos", 0))
                avg_price = float(pos.get("avgPx", 0))
                notional_value = abs(size * avg_price)
                
                # Get actual margin requirement from OKX
                initial_margin = float(pos.get("imr", 0))  # Initial margin requirement
                maintenance_margin = float(pos.get("mmr", 0))  # Maintenance margin requirement
                
                # Calculate actual leverage
                actual_leverage = notional_value / initial_margin if initial_margin > 0 else 0
                
                positions.append({
                    "instId": pos.get("instId"),
                    "side": pos.get("posSide"), 
                    "size": size,
                    "avgPx": avg_price,
                    "notional_value": notional_value,
                    "initial_margin": initial_margin,
                    "maintenance_margin": maintenance_margin,
                    "actual_leverage": actual_leverage,
                    "upl": float(pos.get("upl", 0)),  # Unrealized PnL
                    "uplRatio": float(pos.get("uplRatio", 0))
                })
        
        print(f"Found {len(positions)} open positions with margin tracking")
        return positions
        
    except Exception as e:
        print(f"Exception fetching positions: {e}")
        return []

def get_actual_leverage_for_symbol(symbol):
    """
    Get the actual leverage being used for a specific symbol by checking open positions.
    Returns the actual leverage or None if no position found.
    """
    positions = get_open_positions()
    
    for pos in positions:
        if pos["instId"] == symbol:
            return pos["actual_leverage"]
    
    return None

def get_leverage_settings(symbol):
    """
    Get current leverage settings for a specific symbol from OKX.
    Returns dict with leverage info or None if failed.
    """
    endpoint = "/api/v5/account/leverage-info"
    url = BASE_URL + endpoint
    
    try:
        # Query specific instrument
        params = {"instId": symbol, "mgnMode": "cross"}
        resp = requests.get(url, headers=_headers("GET", endpoint), params=params)
        data = resp.json()
        
        if data.get("code") != "0":
            print(f"Error fetching leverage for {symbol}: {data.get('msg', 'Unknown error')}")
            return None
            
        if data.get("data"):
            lever_info = data["data"][0]
            return {
                "symbol": symbol,
                "current_leverage": float(lever_info.get("lever", 0)),
                "max_leverage": float(lever_info.get("leverMax", 0)),
                "margin_mode": lever_info.get("mgnMode", ""),
                "position_side": lever_info.get("posSide", "")
            }
        
        return None
        
    except Exception as e:
        print(f"Exception fetching leverage for {symbol}: {e}")
        return None

def get_instrument_details(symbol):
    """
    Get detailed instrument information including margin requirements from OKX.
    Returns dict with instrument specs or None if failed.
    """
    endpoint = "/api/v5/public/instruments"
    url = BASE_URL + endpoint
    
    try:
        params = {"instType": "SWAP", "instId": symbol}
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if data.get("code") != "0":
            print(f"Error fetching instrument details for {symbol}: {data.get('msg', 'Unknown error')}")
            return None
            
        if data.get("data"):
            inst_info = data["data"][0]
            return {
                "symbol": symbol,
                "contract_val": float(inst_info.get("ctVal", 0)),
                "min_size": float(inst_info.get("minSz", 0)),
                "lot_size": float(inst_info.get("lotSz", 0)),
                "tick_size": float(inst_info.get("tickSz", 0)),
                "max_leverage": float(inst_info.get("lever", 0)),
                "contract_type": inst_info.get("ctType", ""),
                "base_currency": inst_info.get("baseCcy", ""),
                "quote_currency": inst_info.get("quoteCcy", "")
            }
        
        return None
        
    except Exception as e:
        print(f"Exception fetching instrument details for {symbol}: {e}")
        return None

def validate_position_with_okx(symbol, proposed_size, entry_price):
    """
    Validate a proposed position against OKX's actual requirements.
    Returns dict with validation results and recommendations.
    """
    print(f"\n🔍 VALIDATING {symbol} POSITION WITH OKX")
    print("="*50)
    
    # Get leverage settings
    leverage_info = get_leverage_settings(symbol)
    if leverage_info:
        print(f"Current Leverage: {leverage_info['current_leverage']}x")
        print(f"Max Leverage: {leverage_info['max_leverage']}x")
        print(f"Margin Mode: {leverage_info['margin_mode']}")
    else:
        print("❌ Could not fetch leverage settings")
    
    # Get instrument details
    inst_details = get_instrument_details(symbol)
    if inst_details:
        print(f"Min Size: {inst_details['min_size']}")
        print(f"Lot Size: {inst_details['lot_size']}")
        print(f"Contract Value: {inst_details['contract_val']}")
        print(f"Max Leverage: {inst_details['max_leverage']}x")
        
        # Validate proposed size
        if proposed_size < inst_details['min_size']:
            print(f"❌ Position too small: {proposed_size} < {inst_details['min_size']} minimum")
            return {"valid": False, "reason": "below_minimum_size", "min_size": inst_details['min_size']}
        
        # Check if size aligns with lot size
        if inst_details['lot_size'] > 0:
            remainder = proposed_size % inst_details['lot_size']
            if remainder != 0:
                adjusted_size = proposed_size - remainder
                print(f"⚠️ Size adjusted for lot requirements: {proposed_size} → {adjusted_size}")
                proposed_size = adjusted_size
    else:
        print("❌ Could not fetch instrument details")
    
    # Calculate margin requirement if we have leverage info
    if leverage_info and leverage_info['current_leverage'] > 0:
        notional_value = proposed_size * entry_price
        estimated_margin = notional_value / leverage_info['current_leverage']
        print(f"Notional Value: ${notional_value:.2f}")
        print(f"Estimated Margin: ${estimated_margin:.2f}")
        
        return {
            "valid": True, 
            "adjusted_size": proposed_size,
            "estimated_margin": estimated_margin,
            "actual_leverage": leverage_info['current_leverage']
        }
    
    print("="*50)
    return {"valid": True, "adjusted_size": proposed_size}

def report_margin_usage():
    """
    Generate a detailed report of actual margin usage across all positions.
    """
    positions = get_open_positions()
    margin_info = get_account_margin_info()
    
    if not margin_info:
        print("❌ Could not get margin info for report")
        return
    
    print("\n" + "="*60)
    print("📊 MARGIN USAGE REPORT")
    print("="*60)
    print(f"Available Margin: ${margin_info['availBal']:.2f}")
    print(f"Total Equity: ${margin_info['totalEq']:.2f}")
    print()
    
    total_margin_used = 0
    
    for pos in positions:
        symbol = pos["instId"]
        notional = pos["notional_value"]
        margin = pos["initial_margin"]
        leverage = pos["actual_leverage"]
        
        total_margin_used += margin
        
        print(f"{symbol}:")
        print(f"  Notional: ${notional:,.2f}")
        print(f"  Margin:   ${margin:.2f}")
        print(f"  Leverage: {leverage:.1f}x")
        print(f"  % of Available: {(margin/margin_info['availBal'])*100:.1f}%")
        print()
    
    print(f"Total Margin Used: ${total_margin_used:.2f}")
    print(f"Margin Utilization: {(total_margin_used/margin_info['availBal'])*100:.1f}%")
    print()
    
    # Show allocation strategy
    from bot.config import config
    margin_per_position_pct = config.get('margin_per_position_pct', 0.10)
    target_per_position = margin_info['availBal'] * margin_per_position_pct
    max_positions = config.get('max_open_trades', 10)
    
    print(f"ALLOCATION STRATEGY:")
    print(f"Target per position: {margin_per_position_pct*100:.0f}% = ${target_per_position:.2f}")
    print(f"Max positions: {max_positions}")
    print(f"Theoretical max usage: ${target_per_position * max_positions:.2f} ({(target_per_position * max_positions / margin_info['availBal'])*100:.0f}%)")
    print("="*60)

