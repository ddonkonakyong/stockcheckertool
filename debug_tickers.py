from utils import fetch_stock_info

def check_ticker(symbol):
    print(f"--- Checking {symbol} ---")
    # Use the robust function
    info = fetch_stock_info(symbol)
    
    if info:
         print(f"Name: {info.get('longName')}")
         print(f"Price: {info.get('currentPrice')}")
         print(f"FCF: {info.get('freeCashFlow')}")
         print(f"Shares: {info.get('sharesOutstanding')}")
    else:
         print("No info returned.")

check_ticker("000660.KS") # KOSPI (SK Hynix)
check_ticker("000660.KQ") # KOSDAQ check
