import yfinance as yf
import pandas as pd

def check_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        print(f"--- Info for {ticker} ---")
        
        # Check cashflow DataFrame
        cf = stock.cashflow
        if not cf.empty:
            print("Cashflow DataFrame Head:")
            print(cf.head())
            
            if 'Free Cash Flow' in cf.index:
                 print(f"Free Cash Flow from DF: {cf.loc['Free Cash Flow'].iloc[0]}")
            else:
                 print(" 'Free Cash Flow' index not found.")
                 if 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
                     ops = cf.loc['Operating Cash Flow'].iloc[0]
                     capex = cf.loc['Capital Expenditure'].iloc[0]
                     fcf = ops + capex
                     print(f"Calculated FCF (Ops + CapEx): {fcf}")
        else:
            print("Cashflow DataFrame is empty")

    except Exception as e:
        print(f"Error: {e}")

check_info("AAPL")
