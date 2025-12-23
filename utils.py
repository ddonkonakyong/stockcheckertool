import yfinance as yf
import pandas as pd
import ta

def fetch_stock_data(ticker, period="1y", interval="1d"):
    """
    Fetches historical stock data for a given ticker.
    """
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return None
        return data
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

def fetch_stock_info(ticker):
    """
    Fetches fundamental info for a given ticker, ensuring FCF is present and Price is accurate.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 1. Update Price from History if needed (often more accurate/realtime for non-US)
        # Fetch 2 days of minute data or 1 day of daily to get latest close
        try:
             # Fast info is often better for last price
             last_price = stock.fast_info.get('last_price')
             if last_price:
                 info['currentPrice'] = last_price
                 info['regularMarketPrice'] = last_price
             else:
                 # Fallback to recent history
                 recent = stock.history(period="5d")
                 if not recent.empty:
                     info['currentPrice'] = recent['Close'].iloc[-1]
                     info['regularMarketPrice'] = recent['Close'].iloc[-1]
        except Exception as e:
            print(f"Error fetching latest price update: {e}")

        # 1. Update Price from History... (kept previous block above)
        # ...

        # 2. Update Shares from fast_info if missing (Crucial for DCF)
        if 'sharesOutstanding' not in info or info['sharesOutstanding'] is None:
             try:
                 shares = stock.fast_info.get('shares')
                 if shares:
                     info['sharesOutstanding'] = shares
             except Exception: pass

        # 3. Robust FCF Extraction
        if 'freeCashFlow' not in info or info['freeCashFlow'] is None:
            try:
                cf = stock.cashflow
                if not cf.empty:
                    # Look for first non-NaN FCF
                    if 'Free Cash Flow' in cf.index:
                        # Iterate cols to find valid value
                        for col in cf.columns:
                            val = cf.loc['Free Cash Flow', col]
                            if pd.notna(val) and val != 0:
                                info['freeCashFlow'] = val
                                break
                                
                    elif 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
                        # Fallback calculation
                         for col in cf.columns:
                             ops = cf.loc['Operating Cash Flow', col]
                             capex = cf.loc['Capital Expenditure', col]
                             if pd.notna(ops) and pd.notna(capex):
                                 info['freeCashFlow'] = ops + capex
                                 break
            except Exception as e:
                print(f"Error extracting FCF from DataFrame: {e}")
                
        # 4. Robust Total Debt/Cash Extraction
        if 'totalDebt' not in info or info['totalDebt'] is None:
             try:
                 # Try key variations
                 if 'totalDebt' in info: del info['totalDebt']
                 
                 bs = stock.balance_sheet
                 if not bs.empty:
                      # Try specific keys in balance sheet
                      if 'Total Debt' in bs.index:
                           info['totalDebt'] = bs.loc['Total Debt'].iloc[0]
                      elif 'Long Term Debt' in bs.index: # Fallback partial
                           info['totalDebt'] = bs.loc['Long Term Debt'].iloc[0]
                           
             except: pass
             
        if 'totalCash' not in info or info['totalCash'] is None:
             try:
                 bs = stock.balance_sheet
                 if not bs.empty:
                      if 'Cash And Cash Equivalents' in bs.index:
                           info['totalCash'] = bs.loc['Cash And Cash Equivalents'].iloc[0]
                      elif 'Cash Cash Equivalents And Short Term Investments' in bs.index:
                           info['totalCash'] = bs.loc['Cash Cash Equivalents And Short Term Investments'].iloc[0]
             except: pass

        return info
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return None

def calculate_indicators(df):
    """
    Adds technical indicators to the dataframe.
    """
    if df is None or df.empty:
        return df
    
    # Ensure we are working with a clean dataframe (sometimes simple Moving Averages fail with multi-level index)
    # yfinance download might return MultiIndex if multiple tickers, but here we just do one.
    # However, sometimes it returns columns like (Adj Close, TICKER).
    # We will assume a single level or handle it if needed, but for now standard ta should work on Series.
    
    # If using yfinance 0.2+, the columns might be multi-level if not flattened.
    # But let's assume standard 'Close' column exists or is accessible.
    
    try:
        # Squeeze if single ticker to avoid multiindex issues usually
        if isinstance(df.columns, pd.MultiIndex):
             df = df.xs(df.columns.levels[1][0], axis=1, level=1)

        # Simple Moving Averages
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        
        # RSI
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        
        # MACD
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
    except Exception as e:
        print(f"Error calculating indicators: {e}")
    
    return df

def calculate_dcf(free_cash_flow, growth_rate, discount_rate, terminal_growth_rate, shares_outstanding, net_debt):
    """
    Calculates the intrinsic value per share using Discounted Cash Flow analysis.
    
    Args:
        free_cash_flow (float): Recent Free Cash Flow.
        growth_rate (float): Expected annual growth rate for the next 5 years (decimal, e.g., 0.10 for 10%).
        discount_rate (float): Discount rate or WACC (decimal, e.g., 0.10 for 10%).
        terminal_growth_rate (float): Terminal growth rate (decimal, e.g., 0.025 for 2.5%).
        shares_outstanding (int): Number of shares outstanding.
        net_debt (float): Total Debt - Total Cash.
        
    Returns:
        float: Intrinsic Value per Share.
    """
    try:
        # Calculate Future Cash Flows for 5 years
        future_cash_flows = []
        for i in range(1, 6):
            fcf = free_cash_flow * ((1 + growth_rate) ** i)
            discounted_fcf = fcf / ((1 + discount_rate) ** i)
            future_cash_flows.append(discounted_fcf)
            
        # Calculate Terminal Value
        terminal_value_fcf = free_cash_flow * ((1 + growth_rate) ** 5) * (1 + terminal_growth_rate)
        terminal_value = terminal_value_fcf / (discount_rate - terminal_growth_rate)
        discounted_terminal_value = terminal_value / ((1 + discount_rate) ** 5)
        
        # Total Enterprise Value
        enterprise_value = sum(future_cash_flows) + discounted_terminal_value
        
        # Equity Value
        equity_value = enterprise_value - net_debt
        
        # Value per Share
        intrinsic_value = equity_value / shares_outstanding
        return intrinsic_value
    except Exception as e:
        print(f"Error calculating DCF: {e}")
        return None

def calculate_wacc(ticker, info=None):
    """
    Calculates Weighted Average Cost of Capital (WACC).
    """
    try:
        if info is None:
            info = fetch_stock_info(ticker)
            if info is None: return None, None, None

        # Cost of Equity (CAPM)
        # Re = Rf + Beta * (Rm - Rf)
        beta = info.get('beta')
        if beta is None:
            return None, None, None
            
        risk_free_rate = 0.0425 # Approx 10y Treasury Yield, can be updated or fetched
        equity_risk_premium = 0.05 # Historical average range 4-6%
        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        
        # Cost of Debt
        # Rd = Interest Expense / Total Debt
        # We need financials for Interest Expense
        stock = yf.Ticker(ticker)
        financials = stock.financials
        interest_expense = 0
        total_debt = info.get('totalDebt')
        
        if not financials.empty:
            # Try to find interest expense (often labeled 'Interest Expense')
            # Look for keys containing 'interest'
            if 'Interest Expense' in financials.index:
                interest_expense = abs(financials.loc['Interest Expense'].iloc[0])
            elif 'Interest Expense Non Operating' in financials.index:
                 interest_expense = abs(financials.loc['Interest Expense Non Operating'].iloc[0])
            # Sometimes it's inside Net Income components, simplified here.
            
        cost_of_debt = 0.0
        if total_debt and total_debt > 0 and interest_expense > 0:
            cost_of_debt = interest_expense / total_debt
        else:
             # Fallback if specific debt cost unavailable
             cost_of_debt = 0.045
        
        tax_rate = 0.21 # Corporate Tax Rate
        
        # WACC
        market_cap = info.get('marketCap')
        if not market_cap or not total_debt:
             # Can't calculate weightings properly, defaulting weight or returning None
             if not market_cap: return None, None, None
             # If no debt, WACC = Re
             if not total_debt: return cost_of_equity, cost_of_equity, 0.0

        total_value = market_cap + total_debt
        equity_weight = market_cap / total_value
        debt_weight = total_debt / total_value
        
        wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
        
        return wacc, cost_of_equity, cost_of_debt
        
    except Exception as e:
        print(f"Error calculating WACC: {e}")
        return None, None, None

def fetch_stock_news(ticker):
    """
    Fetches latest news for a given ticker.
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        return news
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []

def fetch_analyst_ratings(ticker):
    """
    Fetches analyst recommendations and upgrades/downgrades.
    """
    rec_summary = None
    upgrades = None
    
    try:
        stock = yf.Ticker(ticker)
        # Recommendations (Strong Buy, Buy, etc.) - DataFrame
        rec_summary = stock.recommendations
        
        # Upgrades/Downgrades - DataFrame
        upgrades = stock.upgrades_downgrades
        
    except Exception as e:
        print(f"Error fetching ratings for {ticker}: {e}")
        
    return rec_summary, upgrades

