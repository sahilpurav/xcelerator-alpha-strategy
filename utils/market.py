import pandas as pd
from logic.indicators import calculate_dma

def is_market_strong(benchmark_df: pd.DataFrame) -> bool:
    """
    Determines if the market is strong based on the benchmark index.
    A strong market is defined as one where the latest close is above the 200-day DMA.
    
    Args:
        benchmark_df (pd.DataFrame): DataFrame containing benchmark prices with 'Close' column.
    
    Returns:
        bool: True if the market is strong, False otherwise.
    """
    if benchmark_df is None or benchmark_df.shape[0] < 200:
        return False

    latest_close = benchmark_df["Close"].iloc[-1]
    dma_200 = calculate_dma(benchmark_df, 200)

    if dma_200 is None:
        return False

    return latest_close >= dma_200