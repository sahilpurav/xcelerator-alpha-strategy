import pandas as pd

from logic.ranking import rank
from utils.market import is_market_strong


def run_strategy(
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    held_symbols: list[str],
    benchmark_symbol: str,
    top_n: int = 15,
    band: int = 5,
    weights: tuple[float, float, float] = (0.8, 0.1, 0.1),
    cash_equivalent: str = "LIQUIDCASE.NS",
    jump_threshold: float = 0.15,
) -> list[dict[str, str | int | None]]:
    """
    Optimized strategy execution in a single function.

    Args:
        price_data: Dictionary of symbol -> DataFrame with OHLCV data
        as_of_date: Date for strategy execution
        held_symbols: Currently held stock symbols
        benchmark_symbol: Symbol for benchmark index (e.g., "^CRSLDX", "^CNX100")
        top_n: Target number of stocks in portfolio
        band: Band size for determining when to sell held stocks
        weights: Tuple of (return_weight, rsi_weight, proximity_weight) for ranking
        cash_equivalent: Symbol to use as cash equivalent
        jump_threshold: Maximum allowed daily return for new entries

    Returns:
        List of recommendation dictionaries with keys: symbol, action, rank
    """

    # Step 1: Check market strength
    market_is_strong = is_market_strong(price_data, benchmark_symbol=benchmark_symbol, as_of_date=as_of_date)

    # Normalize cash symbol once
    cash_symbol_clean = cash_equivalent.replace(".NS", "")

    # If market is weak, liquidate all positions and invest in cash equivalent
    if not market_is_strong:
        return (
            # Sell all non-cash holdings
            [
                {"symbol": sym, "action": "SELL", "rank": None}
                for sym in held_symbols
                if sym != cash_symbol_clean
            ]
            +
            # Handle cash position
            [
                {
                    "symbol": cash_symbol_clean,
                    "action": "HOLD" if cash_symbol_clean in held_symbols else "BUY",
                    "rank": None,
                }
            ]
        )

    # Step 2: Optimize ranking data preparation
    ranked_df = rank(price_data, as_of_date, weights)

    # Single-pass data preparation (eliminating redundant operations)
    ranked_df_clean = ranked_df.copy()
    ranked_df_clean["symbol"] = ranked_df_clean["symbol"].str.replace(
        ".NS", "", regex=False
    )
    ranked_df_clean = ranked_df_clean.reset_index(drop=True)
    ranked_df_clean["rank"] = ranked_df_clean.index + 1

    # Pre-compute lookups for O(1) access
    symbols_ranked = ranked_df_clean["symbol"].tolist()
    symbols_ranked_set = set(symbols_ranked)  # O(1) membership testing
    rank_lookup = dict(zip(ranked_df_clean["symbol"], ranked_df_clean["rank"]))
    top_n_symbols = ranked_df_clean.head(top_n)["symbol"].tolist()

    # Step 3: Categorize held stocks using optimized lookups
    held_stocks = []
    removed_stocks = []

    for sym in held_symbols:
        if sym == cash_symbol_clean:
            removed_stocks.append(sym)
        elif sym in symbols_ranked_set:  # O(1) instead of O(n)
            rank_pos = rank_lookup[sym]  # O(1) instead of DataFrame lookup
            (held_stocks if rank_pos <= top_n + band else removed_stocks).append(sym)
        else:
            removed_stocks.append(sym)

    # Step 4: Determine new entries with optimized filtering
    held_stocks_set = set(held_stocks)  # O(1) membership testing
    max_new_entries = top_n - len(held_stocks)
    raw_new_entries = [s for s in top_n_symbols if s not in held_stocks_set][
        :max_new_entries
    ]

    # Step 5: Filter high-jump stocks with optimized date handling
    new_entries = []
    for symbol in raw_new_entries:
        symbol_ns = symbol if ".NS" in symbol else f"{symbol}.NS"
        df = price_data.get(symbol_ns)

        # Quick validation checks
        if df is None or as_of_date not in df.index:
            new_entries.append(symbol)
            continue

        try:
            current_idx = df.index.get_loc(as_of_date)
            if current_idx == 0:
                new_entries.append(symbol)
                continue

            prev_date = df.index[current_idx - 1]
            prev_close = df.loc[prev_date, "Close"]
            curr_close = df.loc[as_of_date, "Close"]
            daily_return = (curr_close / prev_close) - 1

            if daily_return <= jump_threshold:
                new_entries.append(symbol)
            else:
                print(
                    f"⚠️ Strategy: Skipping {symbol} on {as_of_date.date()} due to large jump of {daily_return:.2%}"
                )

        except (KeyError, IndexError):
            new_entries.append(symbol)

    # Step 6: Build recommendations using list comprehensions for efficiency
    return (
        # SELL recommendations
        [
            {"symbol": sym, "action": "SELL", "rank": rank_lookup.get(sym)}
            for sym in removed_stocks
        ]
        +
        # HOLD recommendations
        [
            {"symbol": sym, "action": "HOLD", "rank": rank_lookup.get(sym)}
            for sym in held_stocks
        ]
        +
        # BUY recommendations
        [
            {"symbol": sym, "action": "BUY", "rank": rank_lookup.get(sym)}
            for sym in new_entries
        ]
    )
