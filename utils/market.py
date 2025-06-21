import pandas as pd
from functools import lru_cache
from datetime import datetime, time
import yfinance as yf
from logic.indicators import calculate_ema, calculate_dma

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

def is_market_strong(price_data: dict[str, pd.DataFrame], benchmark_symbol: str = "^CRSLDX", as_of_date: pd.Timestamp = None, breadth_threshold: float = 0.4) -> bool:
    """
    Determines if the market is strong based on benchmark index and market breadth.
    
    Market is weak if ANY of the below conditions are met:
    1. Benchmark price is below 22, 44, AND 66 DMA (all three conditions)
    2. Market breadth ratio is below the threshold
    
    Args:
        price_data (dict): Dictionary of symbol -> OHLCV DataFrame (must include benchmark symbol)
        benchmark_symbol (str): Symbol for benchmark index (default: "^CRSLDX")
        as_of_date (pd.Timestamp, optional): Date to calculate metrics for
        breadth_threshold (float): Minimum breadth ratio required (default: 0.5 = 50%)
    
    Returns:
        bool: True if the market is strong, False otherwise.
    """
    # Get benchmark data from price_data
    benchmark_df = price_data.get(benchmark_symbol)
    if benchmark_df is None:
        raise ValueError(f"Benchmark data ({benchmark_symbol}) not found in price_data.")
    
    # Filter benchmark data up to as_of_date if provided
    if as_of_date is not None:
        benchmark_df = benchmark_df[benchmark_df.index <= as_of_date]
    
    if benchmark_df.shape[0] < 66:
        return False

    latest_close = benchmark_df["Close"].iloc[-1]
    ema_22 = calculate_ema(benchmark_df, 22)
    ema_44 = calculate_ema(benchmark_df, 44)
    ema_66 = calculate_ema(benchmark_df, 66)

    if ema_22 is None or ema_44 is None or ema_66 is None:
        return False

    # Check benchmark condition: Market is weak if price is below ALL three EMAs
    benchmark_weak = (latest_close < ema_22 and 
                     latest_close < ema_44 and 
                     latest_close < ema_66)
    
    if benchmark_weak:
        print("⚠️ Market is weak (benchmark below all EMAs), skipping ranking.")
        return False
    
    # Check market breadth
    breadth_ratio = _get_market_breadth_ratio(price_data, dma_period=50, as_of_date=as_of_date)
    
    if breadth_ratio < breadth_threshold:
        print(f"Market breadth is weak ({breadth_ratio:.2%} < {breadth_threshold:.0%}), skipping ranking.")
        return False
    
    print(f"💪 Market is strong: Benchmark above EMAs and breadth ratio is {breadth_ratio:.2%}.")
    return True

def _get_market_breadth_ratio(price_data: dict[str, pd.DataFrame], dma_period: int = 50, as_of_date: pd.Timestamp = None) -> float:
    """
    Calculates the percentage of stocks trading above their n-day DMA as of a specific date.
    Excludes benchmark indices (^CRSLDX) from the calculation.
    
    Args:
        price_data: Dictionary of symbol -> OHLCV DataFrame
        dma_period: DMA period to use (e.g., 50, 200)
        as_of_date: Date to calculate the ratio for (if None, uses latest available data)
    
    Returns:
        float: Ratio of stocks above their DMA (between 0.0 and 1.0)
    """
    count_above_dma = 0
    total = 0

    for symbol, df in price_data.items():
        # Skip benchmark data
        if symbol.startswith("^"):
            continue
        
        # Filter data up to the as_of_date if provided
        if as_of_date is not None:
            df = df[df.index <= as_of_date]
            
        if df.shape[0] < dma_period:
            continue

        dma = calculate_dma(df, dma_period)
        if dma is None:
            continue

        # Use the latest close price in the filtered dataframe (as of the specified date)
        current_price = df["Close"].iloc[-1]
        if current_price > dma:
            count_above_dma += 1

        total += 1

    return count_above_dma / total if total > 0 else 0.0