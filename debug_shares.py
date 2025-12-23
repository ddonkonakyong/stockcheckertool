from utils import fetch_stock_info
import yfinance as yf

def check_shares(ticker):
    print(f"--- Checking Shares for {ticker} ---")
    stock = yf.Ticker(ticker)
    
    # Check standard info
    try:
        info_shares = stock.info.get('sharesOutstanding')
        print(f"Info Shares: {info_shares}")
    except:
        print("Info fetch failed")
        
    # Check fast_info
    try:
        fast_shares = stock.fast_info.get('shares')
        print(f"Fast Info Shares: {fast_shares}")
    except Exception as e:
        print(f"Fast Info failed: {e}")

check_shares("000660.KS")
