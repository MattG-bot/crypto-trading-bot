import hmac
import hashlib
from datetime import datetime

# Replace these with your actual API secret and example values
API_SECRET = "your_api_secret_here"
HTTP_METHOD = "GET"
REQUEST_PATH = "/api/v5/account/balance"
REQUEST_BODY = ""  # Empty string for GET requests

def get_timestamp():
    return datetime.utcnow().isoformat("T", "milliseconds") + "Z"

def sign(message, secret):
    # Explicit UTF-8 encoding
    return hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

def main():
    timestamp = get_timestamp()
    message = f"{timestamp}{HTTP_METHOD}{REQUEST_PATH}{REQUEST_BODY}"

    print(f"Timestamp: {timestamp}")
    print(f"Message to sign (repr): {repr(message)}")
    print(f"Secret (repr): {repr(API_SECRET)}")

    signature = sign(message, API_SECRET)
    print(f"Signature: {signature}")

if __name__ == "__main__":
    main()
