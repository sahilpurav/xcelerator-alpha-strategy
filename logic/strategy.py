import pandas as pd
from utils.market import is_market_strong
from logic.ranking import rank

def get_ranked_stocks(price_data: dict[str, pd.DataFrame], as_of_date: pd.Timestamp) -> pd.DataFrame:
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

    ranked["rank"] = ranked["total_rank"].rank(method="first").astype(int)
    return ranked  # return full list

def generate_band_adjusted_portfolio(
    ranked_df: pd.DataFrame,
    prev_holdings: list[str],
    top_n: int = 15,
    band: int = 5
) -> tuple[list[str], list[str], list[str], list[str]]:
    """
    Applies band logic to generate final portfolio.
    
    Returns:
        held_stocks, new_entries, removed_stocks, final_portfolio
    """
    ranked_df = ranked_df.reset_index(drop=True)
    ranked_df["rank"] = ranked_df.index + 1
    ranked_df["symbol"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    symbols_ranked = ranked_df["symbol"].tolist()

    held_stocks = []
    removed_stocks = []

    for sym in prev_holdings:
        if sym in symbols_ranked:
            rank = ranked_df.loc[ranked_df["symbol"] == sym, "rank"].values[0]
            if rank <= top_n + band:
                held_stocks.append(sym)
            else:
                removed_stocks.append(sym)
        else:
            removed_stocks.append(sym)

    top_n_symbols = ranked_df.head(top_n)["symbol"].tolist()
    new_entries = [s for s in top_n_symbols if s not in held_stocks][: top_n - len(held_stocks)]
    final_portfolio = held_stocks + new_entries

    return held_stocks, new_entries, removed_stocks, final_portfolio