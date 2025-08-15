from bot.exchange_okx import get_account_equity

if __name__ == "__main__":
    try:
        equity = get_account_equity()
        print(f"Account USDT equity: {equity}")
    except Exception as e:
        print(f"Error fetching account equity: {e}")

