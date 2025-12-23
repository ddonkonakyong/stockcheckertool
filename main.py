import streamlit as st
import plotly.graph_objects as go
from utils import fetch_stock_data, fetch_stock_info, calculate_indicators, calculate_dcf, calculate_wacc, fetch_stock_news
from datetime import datetime

def plot_chart(df, ticker):
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price'))
    
    # SMA
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='SMA 20'))
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='SMA 50'))
        
    fig.update_layout(title=f'{ticker} Price Chart', yaxis_title='Price', xaxis_title='Date', template='plotly_dark')
    return fig

def main():
    st.set_page_config(page_title="Stock Analysis Tool", layout="wide")
    st.title("Stock Analysis Dashboard")
    
    # Sidebar
    st.sidebar.header("User Input")
    market = st.sidebar.selectbox("Market", ["US", "Korea (KOSPI)", "Korea (KOSDAQ)"])
    ticker_input = st.sidebar.text_input("Enter Stock Ticker", "AAPL").upper()
    
    ticker = ticker_input
    if market == "Korea (KOSPI)":
        if not ticker.endswith(".KS"): ticker += ".KS"
    elif market == "Korea (KOSDAQ)":
        if not ticker.endswith(".KQ"): ticker += ".KQ"
        
    period = st.sidebar.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3)
    interval = st.sidebar.selectbox("Interval", ["1d", "1wk", "1mo"], index=0)
    
    
    if st.sidebar.button("Analyze"):
        with st.spinner('Fetching data...'):
            # Fetch Data
            df = fetch_stock_data(ticker, period, interval)
            info = fetch_stock_info(ticker)
            
            if df is not None:
                st.session_state['data'] = df
                st.session_state['info'] = info
                st.session_state['ticker'] = ticker
                
                # Calculate WACC
                wacc, re, rd = calculate_wacc(ticker, info)
                st.session_state['wacc_data'] = {'wacc': wacc, 're': re, 'rd': rd}
                
                # Fetch News (and cache it)
                try:
                    news = fetch_stock_news(ticker)
                    st.session_state['news'] = news
                except:
                    st.session_state['news'] = []
            else:
                st.error("Error fetching data. Please check the ticker symbol.")

    if 'data' in st.session_state:
        df = st.session_state['data']
        info = st.session_state['info']
        display_ticker = st.session_state['ticker'] # Use stored ticker for logic
        
        # Calculate Indicators (in case we didn't store them or want to recalc)
        # It's better to calc once and store, but adding it here is fast enough usually.
        # Let's perform calculation if columns missing
        if 'SMA_20' not in df.columns:
             df = calculate_indicators(df)

        # Display Info
        price = 'N/A'
        if info:
            col1, col2, col3 = st.columns(3)
            # Handle cases where keys might be missing or different
            price = info.get('currentPrice') or info.get('regularMarketPrice') or 'N/A'
            mkt_cap = info.get('marketCap', 'N/A')
            high_52 = info.get('fiftyTwoWeekHigh') or info.get('regularMarketDayHigh') or 'N/A' # 52 wk high might be under different key
            
            # Determine Currency Symbol
            currency_symbol = "$"
            if info.get('currency') == 'KRW':
                currency_symbol = "₩"

            # Helper for formatting
            def fmt_currency(val):
                if isinstance(val, (int, float)):
                    return f"{currency_symbol}{val:,.2f}"
                return val
            
            def fmt_large(val):
                if isinstance(val, (int, float)):
                    return f"{currency_symbol}{val:,}"
                return val

            col1.metric("Current Price", fmt_currency(price))
            col2.metric("Market Cap", fmt_large(mkt_cap))
            col3.metric("52 Week High", fmt_currency(high_52))
        
        # Navigation using Radio for persistence
        view = st.radio("View", ["Charts", "Technical Analysis", "Valuation (DCF)", "Latest News"], horizontal=True, key="view_nav")

        if view == "Charts":
            # Plot Chart
            st.plotly_chart(plot_chart(df, display_ticker), use_container_width=True)
            # Show Data
            st.subheader("Historical Data")
            st.dataframe(df.tail())

        elif view == "Technical Analysis":
            st.subheader("Technical Indicators")
            sub_tab1, sub_tab2 = st.tabs(["RSI", "MACD"])
            
            with sub_tab1:
                if 'RSI' in df.columns:
                    st.line_chart(df['RSI'])
            
            with sub_tab2:
                if 'MACD' in df.columns:
                    st.line_chart(df[['MACD', 'MACD_Signal']])
        
        elif view == "Valuation (DCF)":
            st.subheader("Discounted Cash Flow (DCF) Analysis")
            if info:
                # Extract inputs with defaults
                fcf = info.get('freeCashFlow')
                shares = info.get('sharesOutstanding')
                total_debt = info.get('totalDebt')
                total_cash = info.get('totalCash')
                
                if fcf and shares:
                    net_debt = (total_debt or 0) - (total_cash or 0)
                    
                    # Retrieve saved state or set defaults
                    saved = st.session_state.get('dcf_state', {})
                    def_growth = saved.get('growth_rate', 10.0)
                    def_term = saved.get('terminal_rate', 2.5)
                    def_wacc = saved.get('discount_rate', 10.0)
                    
                    # WACC Logic override if new WACC data exists and no saved override
                    # Actually, let's just default to saved if existing, else calculated WACC
                    if 'wacc_data' in st.session_state and st.session_state['wacc_data']['wacc'] is not None and 'discount_rate' not in saved:
                         def_wacc = st.session_state['wacc_data']['wacc'] * 100

                    with st.form("dcf_form"):
                        col_a, col_b, col_c = st.columns(3)
                        
                        with col_a:
                            growth_rate_input = st.number_input("Growth Rate (Next 5 Years) %", value=float(def_growth), step=0.5)
                        with col_b:
                            terminal_rate_input = st.number_input("Terminal Growth Rate %", value=float(def_term), step=0.1)
                        with col_c:
                            discount_rate_input = st.number_input("Discount Rate (WACC) %", value=float(f"{def_wacc:.2f}"), step=0.5)
                            
                            if 'wacc_data' in st.session_state and st.session_state['wacc_data']['wacc'] is not None:
                                 w_data = st.session_state['wacc_data']
                                 st.caption(f"Calculated WACC: {w_data['wacc']*100:.2f}%")

                        submitted = st.form_submit_button("Calculate Valuaton")
                    
                    if submitted:
                        # Convert to decimal
                        g_rate = growth_rate_input / 100
                        t_rate = terminal_rate_input / 100
                        d_rate = discount_rate_input / 100
                        
                        intrinsic_value = calculate_dcf(fcf, g_rate, d_rate, t_rate, shares, net_debt)
                        
                        # Save State
                        st.session_state['dcf_state'] = {
                            'growth_rate': growth_rate_input,
                            'terminal_rate': terminal_rate_input,
                            'discount_rate': discount_rate_input,
                            'result': intrinsic_value
                        }
                    
                    # Display Result (from session state if available)
                    current_state = st.session_state.get('dcf_state', {})
                    if 'result' in current_state:
                        res = current_state['result']
                        
                        # Re-determine symbol here as it's inside a different block or ensure scope availability
                        currency_symbol = "$"
                        if info.get('currency') == 'KRW':
                             currency_symbol = "₩"
                             
                        if res:
                            st.metric("Intrinsic Value per Share", f"{currency_symbol}{res:,.2f}", delta=f"{((res - price)/price)*100:.2f}%" if isinstance(price, (int, float)) else None)
                            st.write(f"**Assumptions used:** Growth: {current_state['growth_rate']}%, Terminal: {current_state['terminal_rate']}%, WACC: {current_state['discount_rate']}%")
                            st.write(f"**Financials:** FCF: {currency_symbol}{fcf:,}, Shares: {shares:,}, Net Debt: {currency_symbol}{net_debt:,}")
                        else:
                            st.error("Could not calculate DCF (Result is None).")

                else:
                    st.warning("Insufficient fundamental data (Free Cash Flow or Shares Outstanding) for DCF.")
            else:
                st.warning("No fundamental info available for DCF.")
                
        elif view == "Latest News":
            st.subheader("Latest News Headlines")
            news_items = st.session_state.get('news', [])
            if news_items:
                for item in news_items:
                    # yfinance news item structure can be flat or nested in 'content'
                    # Try flat first (older versions)
                    title = item.get('title')
                    publisher = item.get('publisher')
                    link = item.get('link')
                    pub_time = item.get('providerPublishTime')
                    
                    # Check for nested 'content' (newer versions)
                    if not title and 'content' in item:
                        c = item['content']
                        title = c.get('title')
                        pub_time = c.get('pubDate') # Format ISO string likely
                        
                        if 'provider' in c:
                             publisher = c['provider'].get('displayName')
                        
                        if 'canonicalUrl' in c:
                             link = c['canonicalUrl'].get('url')
                        elif 'clickThroughUrl' in c and c['clickThroughUrl']:
                             link = c['clickThroughUrl'].get('url')

                    # Formatting Time
                    time_str = "Recent"
                    if pub_time:
                        try:
                             if isinstance(pub_time, int):
                                 dt_object = datetime.fromtimestamp(pub_time)
                                 time_str = dt_object.strftime("%Y-%m-%d %H:%M")
                             else:
                                 # ISO format string '2025-12-19T21:38:00Z'
                                 dt_object = datetime.strptime(pub_time.replace('Z', '+0000'), "%Y-%m-%dT%H:%M:%S%z")
                                 time_str = dt_object.strftime("%Y-%m-%d %H:%M")
                        except: pass

                    if title:
                        with st.expander(f"{time_str} - {title}"):
                            st.write(f"**Source:** {publisher}")
                            if link:
                                st.markdown(f"[Read full article]({link})")
                            else:
                                st.write("No link available")
            else:
                st.info("No news found for this ticker.")

if __name__ == "__main__":
    main()
