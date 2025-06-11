import pandas as pd
from logic.indicators import calculate_ema

def is_market_strong(benchmark_df: pd.DataFrame) -> bool:
    """
    Determines if the market is strong based on the benchmark index.
    Market is weak if ALL the below conditions are met (AND condition):
    1. The price is below 22 DMA
    2. The price is below 44 DMA
    3. The price is below 66 DMA
    Otherwise market is strong.
    
    Args:
        benchmark_df (pd.DataFrame): DataFrame containing benchmark prices with 'Close' column.
    
    Returns:
        bool: True if the market is strong, False otherwise.
    """
    if benchmark_df is None or benchmark_df.shape[0] < 66:
        return False

    latest_close = benchmark_df["Close"].iloc[-1]
    ema_22 = calculate_ema(benchmark_df, 22)
    ema_44 = calculate_ema(benchmark_df, 44)
    ema_66 = calculate_ema(benchmark_df, 66)

    if ema_22 is None or ema_44 is None or ema_66 is None:
        return False

    # Market is weak if price is below ALL three DMAs
    is_weak = (latest_close < ema_22 and 
               latest_close < ema_44 and 
               latest_close < ema_66)
    
    # Return True for strong market (not weak)
    return not is_weak