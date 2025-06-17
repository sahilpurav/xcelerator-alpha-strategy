import pandas as pd
from typing import Tuple, Dict, List
from utils.market import is_market_strong
from logic.ranking import rank

def run_strategy(
    price_data: Dict[str, pd.DataFrame], 
    as_of_date: pd.Timestamp,
    held_symbols: List[str],
    top_n: int = 15,
    band: int = 5,
    weights: Tuple[float, float, float] = (0.8, 0.1, 0.1)
) -> Tuple[List[str], List[str], List[str], List[str], pd.DataFrame]:
    """
    Complete strategy execution: market filter + ranking + portfolio construction.
    
    Args:
        price_data: Dictionary of symbol -> DataFrame with OHLCV data
        as_of_date: Date for strategy execution
        held_symbols: Currently held stock symbols
        top_n: Target number of stocks in portfolio
        band: Band size for determining when to sell held stocks
        weights: Tuple of (return_weight, rsi_weight, proximity_weight) for ranking
    
    Returns:
        Tuple of (held_stocks, new_entries, removed_stocks, final_portfolio, ranked_df)
    """
    # Step 1: Check market strength
    if not is_market_strong(price_data, benchmark_symbol="^CRSLDX", as_of_date=as_of_date):
        return [], [], held_symbols, [], pd.DataFrame()  # Exit all positions in weak market

    # Step 2: Rank stocks
    ranked_df = rank(price_data, as_of_date, weights)
    ranked_df["rank"] = ranked_df["total_rank"].rank(method="first").astype(int)
    
    # Step 3: Apply band logic for portfolio construction
    ranked_df_work = ranked_df.reset_index(drop=True)
    ranked_df_work["rank"] = ranked_df_work.index + 1
    ranked_df_work["symbol"] = ranked_df_work["symbol"].str.replace(".NS", "", regex=False)
    symbols_ranked = ranked_df_work["symbol"].tolist()

    held_stocks = []
    removed_stocks = []

    # Check which held stocks to keep or remove
    for sym in held_symbols:
        if sym in symbols_ranked:
            rank_pos = ranked_df_work.loc[ranked_df_work["symbol"] == sym, "rank"].values[0]
            if rank_pos <= top_n + band:
                held_stocks.append(sym)
            else:
                removed_stocks.append(sym)
        else:
            removed_stocks.append(sym)

    # Determine new entries
    top_n_symbols = ranked_df_work.head(top_n)["symbol"].tolist()
    new_entries = [s for s in top_n_symbols if s not in held_stocks][: top_n - len(held_stocks)]
    final_portfolio = held_stocks + new_entries

    return held_stocks, new_entries, removed_stocks, final_portfolio, ranked_df