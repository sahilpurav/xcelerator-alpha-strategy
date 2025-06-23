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
    weights: Tuple[float, float, float] = (0.8, 0.1, 0.1),
    cash_equivalent: str = "LIQUIDBEES.NS"
) -> Tuple[List[dict], str, List[str], List[str], List[str], List[str], pd.DataFrame]:
    """
    Complete strategy execution: market filter + ranking + portfolio construction.
    Returns both recommendations format and legacy portfolio composition format.
    
    Args:
        price_data: Dictionary of symbol -> DataFrame with OHLCV data
        as_of_date: Date for strategy execution
        held_symbols: Currently held stock symbols
        top_n: Target number of stocks in portfolio
        band: Band size for determining when to sell held stocks
        weights: Tuple of (return_weight, rsi_weight, proximity_weight) for ranking
        cash_equivalent: Symbol to use as cash equivalent (default: "LIQUIDBEES.NS")
    
    Returns:
        Tuple of:
        - recommendations: List of dictionaries with keys: symbol, action
        - market_regime: String indicating "STRONG" or "WEAK" market
        - held_stocks: List of held stocks that remain in portfolio
        - new_entries: List of new stocks to buy
        - removed_stocks: List of stocks to remove from portfolio
        - final_portfolio: List of final portfolio stocks
        - ranked_df: DataFrame with stock rankings
    """
    # Check if we're already primarily in cash
    cash_symbol_clean = cash_equivalent.replace(".NS", "")
    is_in_cash = cash_symbol_clean in held_symbols and len(held_symbols) == 1
    
    # Step 1: Check market strength
    market_is_strong = is_market_strong(price_data, benchmark_symbol="^CRSLDX", as_of_date=as_of_date)
    market_regime = "STRONG" if market_is_strong else "WEAK"
    
    # Initialize empty dataframe for weak market
    empty_df = pd.DataFrame()
    
    # If market is weak, handle cash transition
    if market_regime == "WEAK":
        # If already in cash, no action needed
        if is_in_cash:
            return [], market_regime, [], [], [], [], empty_df
            
        # Otherwise, sell everything except cash equivalent
        recommendations = [
            {"symbol": symbol, "action": "SELL"}
            for symbol in held_symbols
            if symbol != cash_symbol_clean
        ]
        # For legacy return format
        return recommendations, market_regime, [], [], held_symbols, [], empty_df

    # At this point, market is STRONG
    
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
        # Skip cash equivalent, it's always removed in strong market
        if sym == cash_symbol_clean:
            removed_stocks.append(sym)
            continue
            
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
    raw_new_entries = [s for s in top_n_symbols if s not in held_stocks][: top_n - len(held_stocks)]

    # Filter out new entries with >15% jump on rebalance day
    new_entries = []
    for symbol in raw_new_entries:
        symbol_ns = symbol if ".NS" in symbol else f"{symbol}.NS"
        df = price_data.get(symbol_ns)
        
        if df is None or as_of_date not in df.index or len(df[:as_of_date]) < 2:
            new_entries.append(symbol)
            continue
            
        # Get sorted dates and find previous trading day
        dates = sorted(df.index)
        current_idx = dates.index(as_of_date)
        if current_idx == 0:  # First day in data
            new_entries.append(symbol)
            continue
            
        prev_close = df.loc[dates[current_idx-1], "Close"]
        curr_close = df.loc[as_of_date, "Close"]
        daily_return = (curr_close / prev_close) - 1
        
        if daily_return > 0.15:
            print(f"⚠️ Strategy: Skipping {symbol} on {as_of_date.date()} due to large jump of {daily_return:.2%}")
        else:
            new_entries.append(symbol)
        
    final_portfolio = held_stocks + new_entries
    
    # Create recommendations list
    recommendations = []
    
    # Add SELL recommendations for removed stocks
    for symbol in removed_stocks:
        recommendations.append({"symbol": symbol, "action": "SELL"})
    
    # Add BUY recommendations for new entries
    for symbol in new_entries:
        recommendations.append({"symbol": symbol, "action": "BUY"})
        
    # Return both recommendation format and legacy portfolio composition format
    return recommendations, market_regime, held_stocks, new_entries, removed_stocks, final_portfolio, ranked_df

