import pandas as pd
from logic.indicators import calculate_ema, calculate_dma

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