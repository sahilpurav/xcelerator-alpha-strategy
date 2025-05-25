import pandas as pd
from utils.market import is_market_strong
from logic.ranking import rank

def run_strategy(price_data: dict[str, pd.DataFrame], as_of_date: pd.Timestamp) -> pd.DataFrame:
    """
    Executes a single rebalance cycle:
    - Checks market regime
    - If strong, ranks stocks
    - Returns top 15 picks as DataFrame
    - Returns empty DataFrame if market is weak
    """    
    benchmark_df = price_data.get("^NSEI")
    
    if benchmark_df is None:
        raise ValueError("Benchmark data (^NSEI) not found in price data.")

    benchmark_df = benchmark_df[benchmark_df.index <= as_of_date]

    if not is_market_strong(benchmark_df):
        return pd.DataFrame()

    # Apply ranking logic
    ranked = rank(price_data, as_of_date)

    # Return top 15
    return ranked.head(15)
