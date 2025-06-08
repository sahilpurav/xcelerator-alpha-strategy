import pandas as pd
from functools import lru_cache
from datetime import datetime, time
import yfinance as yf

@lru_cache(maxsize=1)
def get_last_trading_day(symbol: str = "^CRSLDX") -> str:
    """
    Returns the last trading day as a string in YYYY-MM-DD format
    using available data from Yahoo Finance for the given index symbol.

    Results are cached in-memory for the duration of the script.
    """
    df = yf.download(symbol, period="7d", interval="1d", progress=False, auto_adjust=False)
    if df.empty:
        raise Exception("Failed to determine last trading day from Yahoo Finance.")
    last_date = df.index[-1]
    return pd.to_datetime(last_date).strftime("%Y-%m-%d")

def is_market_open_now() -> bool:
    """
    Returns True if current time is during Indian market hours (9:15 AM to 3:30 PM IST)
    AND today is the actual trading day based on NSE calendar (using get_last_trading_day).
    
    This avoids false positives on NSE holidays that fall on weekdays.
    """
    now = datetime.now().astimezone()
    
    # Fast exit on weekends
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Fast exit outside market hours
    if not (time(9, 15) <= now.time() < time(15, 30)):
        return False
    
    # Now check if today is an actual NSE trading day
    india_today_str = now.strftime('%Y-%m-%d')
    last_trading_day_str = get_last_trading_day()

    return india_today_str == last_trading_day_str
