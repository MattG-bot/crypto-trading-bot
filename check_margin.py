#!/usr/bin/env python3
# Check available margin on OKX account

import requests
import json
from bot.exchange_okx import _headers, BASE_URL

def check_account_margin():
    """Check available margin and account details."""
    try:
        # Get account balance details
        endpoint = "/api/v5/account/balance"
        url = BASE_URL + endpoint
        resp = requests.get(url, headers=_headers("GET", endpoint))
        data = resp.json()
        
        print("=== OKX Account Margin Status ===")
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get('code') == '0' and data.get('data'):
            account_data = data['data'][0]
            details = account_data.get('details', [])
            
            # Find USDT details
            usdt_data = next((item for item in details if item.get('ccy') == 'USDT'), None)
            
            if usdt_data:
                print(f"\n=== USDT Margin Details ===")
                print(f"Currency: {usdt_data.get('ccy')}")
                print(f"Available Balance: ${float(usdt_data.get('availBal', 0)):.2f}")
                print(f"Cash Balance: ${float(usdt_data.get('cashBal', 0)):.2f}")  
                print(f"Equity: ${float(usdt_data.get('eq', 0)):.2f}")
                print(f"Frozen: ${float(usdt_data.get('frozenBal', 0)):.2f}")
                print(f"Available for Orders: ${float(usdt_data.get('availEq', 0)):.2f}")
        else:
            print(f"Error: {data}")
            
    except Exception as e:
        print(f"Error checking margin: {e}")

if __name__ == "__main__":
    check_account_margin()