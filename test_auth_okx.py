import os
from dotenv import load_dotenv

load_dotenv()

OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE")

print("API Key:", OKX_API_KEY)
print("API Secret:", (OKX_API_SECRET[:4] + "..." if OKX_API_SECRET else None))
print("API Passphrase:", OKX_API_PASSPHRASE)
import time
import uuid
import hmac
import hashlib
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env file

OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_API_SECRET = os.getenv("OKX_API_SECRET")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE")
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
    print(f"Message: {message}")
    print(f"Signature: {signature}")

    return {
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_account_balance():
    endpoint = "/api/v5/account/balance"
    url = BASE_URL + endpoint
    headers = _headers("GET", endpoint)
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response JSON: {response.json()}")

if __name__ == "__main__":
    get_account_balance()
