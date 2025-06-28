import math

import pandas as pd


def plan_equity_investment(
    symbols: list[str],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    total_capital: float,
    ranked_df: pd.DataFrame,
    transaction_cost_pct: float = 0.001190,
) -> pd.DataFrame:
    """
    Generates an execution plan for first-time investment in selected stocks.
    Uses a 2-step approach:
    1. Allocates capital equally across the given symbols
    2. Uses _maximize_capital_deployment to maximize capital utilization

    Parameters:
    - symbols: List of selected stock symbols (e.g., ['TCS', 'INFY'])
    - price_data: Dictionary mapping symbols to their historical price DataFrames
    - as_of_date: Timestamp representing the date for which prices are used
    - total_capital: Total capital to be deployed
    - transaction_cost_pct: Percentage of transaction cost per trade (default 0.119%)

    Returns:
    - DataFrame with execution plan containing columns:
      ['Symbol', 'Rank', 'Action', 'Price', 'Quantity', 'Invested', 'Weight %']
    """

    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Reserve transaction costs upfront
    transaction_cost_reserve = total_capital * transaction_cost_pct
    investable_capital = total_capital - transaction_cost_reserve

    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
    ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))

    # Step 1: Initial equal allocation to identify purchasable stocks
    per_stock_alloc = investable_capital / len(symbols) if symbols else 0

    # First pass: Identify which stocks can actually be purchased with initial allocation
    purchasable_stocks = []
    for symbol in symbols:
        sym_clean = symbol.replace(".NS", "")
        price = latest_close.get(sym_clean)

        if not price or price == 0:
            continue

        # Check if we can buy at least 1 share with the per-stock allocation
        if per_stock_alloc >= price:
            purchasable_stocks.append(sym_clean)

    if not purchasable_stocks:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    # Step 2: Create initial holdings DataFrame for _maximize_capital_deployment
    initial_holdings = []
    for sym_clean in purchasable_stocks:
        price = latest_close.get(sym_clean)
        if price and price > 0:
            # Start with 0 quantity for new investments
            initial_holdings.append({
                "symbol": sym_clean,
                "price": price,
                "current_value": 0.0  # Starting with no holdings
            })

    df_holdings = pd.DataFrame(initial_holdings)

    if df_holdings.empty:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    # Step 3: Use _maximize_capital_deployment to maximize capital utilization
    execution_data = _maximize_capital_deployment(
        df_holdings, investable_capital
    )

    # Step 4: Add rank information to execution data
    for order in execution_data:
        order["Rank"] = rank_map.get(order["Symbol"], "N/A")

    # Step 5: Final formatting
    if execution_data:
        df_exec = pd.DataFrame(execution_data)
        total_value = df_exec["Invested"].sum()
        df_exec["Weight %"] = df_exec["Invested"] / total_value * 100
    else:
        df_exec = pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    return df_exec


def _fill_underweight_gaps_only(
    targets: list[dict], total_capital: float, target_weight_value: float, rank_map: dict = None
) -> list[dict]:
    """
    Conservative allocation strategy: Only fills gaps for underweight holdings.

    Used by rebalance logic where we want targeted, controlled allocation
    without over-deploying capital. This function stops after filling
    underweight gaps and doesn't attempt to maximize capital deployment.

    Strategy:
    - Only targets underweight holdings (current_value < target_weight_value)
    - Sorts by gap size (largest gaps first) and fills sequentially
    - Conservative approach - no aggressive deployment

    Parameters:
    - targets: List of dicts with keys 'symbol', 'price', 'current_value'
    - total_capital: Total capital available for allocation
    - target_weight_value: Target weight value for each stock (already calculated)
    - rank_map: Dictionary mapping symbols to their ranks (optional)

    Returns:
    - List of dicts with keys: Symbol, Rank, Action, Price, Quantity, Invested
    """

    # Handle empty targets list
    if not targets:
        return []

    df = pd.DataFrame(targets)

    # Validate required columns exist
    required_cols = ["symbol", "price", "current_value"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return []

    # Filter only underweight holdings (should already be filtered, but double-check)
    df = df[df["current_value"] < target_weight_value].copy()
    df["gap"] = target_weight_value - df["current_value"]
    
    # Sort by gap size (largest gaps first)
    df.sort_values("gap", inplace=True, ascending=False)
    
    execution_data = []
    remaining_capital = total_capital

    # Try to fill each stock sequentially, starting with largest gaps
    for _, row in df.iterrows():
        if remaining_capital <= 0:
            break
            
        symbol = row["symbol"]
        price = row["price"]
        gap = row["gap"]
        
        # Calculate how many shares we can buy with remaining capital
        max_shares = int(remaining_capital // price)
        
        # Calculate how many shares we need to fill the gap
        shares_needed = int(gap // price)
        
        # Buy the minimum of what we can afford and what we need
        shares_to_buy = min(max_shares, shares_needed)
        
        if shares_to_buy > 0:
            invested = shares_to_buy * price
            remaining_capital -= invested
            
            execution_data.append(
                {
                    "Symbol": symbol,
                    "Rank": rank_map.get(symbol, "N/A") if rank_map else "N/A",
                    "Action": "BUY",
                    "Price": round(price, 2),
                    "Quantity": shares_to_buy,
                    "Invested": round(invested, 2),
                }
            )

    return execution_data


def _maximize_capital_deployment(
    df_holdings: pd.DataFrame,
    additional_capital: float,
    target_weight_value: float = None,
) -> list[dict]:
    """
    Aggressive deployment strategy: 2-step approach to maximize capital utilization.

    Step 1: Fill underweight holdings using existing _fill_underweight_gaps_only function
    Step 2: Distribute remaining capital equally across all stocks in portfolio
    Step 3: Continue until remaining cash is minimal

    Used by top-up logic where we want to deploy as much capital as possible
    while maintaining approximate equal weighting.

    Parameters:
    - df_holdings: DataFrame with columns 'symbol', 'price', 'current_value'
    - additional_capital: Total capital to be invested (already net of transaction costs)
    - target_weight_value: Target weight value for each stock (optional, calculated if not provided)

    Returns:
    - List of execution orders with Symbol, Action, Price, Quantity, Invested
    """

    if df_holdings.empty:
        return []

    # Calculate target weight if not provided
    if target_weight_value is None:
        total_value = df_holdings["current_value"].sum() + additional_capital
        target_weight_value = total_value / len(df_holdings)

    execution_data = []
    remaining_capital = additional_capital

    # Step 1: Fill underweight holdings using existing function
    # Convert DataFrame to list format expected by _fill_underweight_gaps_only
    all_targets = df_holdings.to_dict('records')
    
    underweight_exec = _fill_underweight_gaps_only(
        all_targets, remaining_capital, target_weight_value
    )
    execution_data.extend(underweight_exec)
    remaining_capital -= sum(row["Invested"] for row in underweight_exec)

    # Step 2: Distribute remaining capital equally across all stocks
    # Continue until remaining capital is minimal (less than price of cheapest stock)
    min_stock_price = df_holdings["price"].min() if not df_holdings.empty else float('inf')
    
    while remaining_capital >= min_stock_price:
        num_stocks = len(df_holdings)
        per_stock_allocation = remaining_capital / num_stocks

        # Track if we made any allocation in this round
        allocated_this_round = False
        round_orders = []

        # Try to allocate equally across all stocks
        for _, row in df_holdings.iterrows():
            price = row["price"]
            
            # Calculate quantity based on per-stock allocation, but at least 1 share
            qty_from_allocation = int(per_stock_allocation // price)
            qty = max(1, qty_from_allocation) if per_stock_allocation >= price else 0

            if qty > 0 and (qty * price) <= remaining_capital:
                invested = qty * price

                round_orders.append(
                    {
                        "Symbol": row["symbol"],
                        "Action": "BUY",
                        "Price": round(price, 2),
                        "Quantity": qty,
                        "Invested": round(invested, 2),
                    }
                )
                allocated_this_round = True

        # If we couldn't allocate to any stock this round, break to avoid infinite loop
        if not allocated_this_round:
            break

        # Add this round's orders to execution data and update remaining capital
        execution_data.extend(round_orders)
        remaining_capital -= sum(order["Invested"] for order in round_orders)

        # If remaining capital is too small, break
        if remaining_capital < min_stock_price:
            break

    # Consolidate orders for same symbol
    consolidated = {}
    for order in execution_data:
        symbol = order["Symbol"]
        if symbol in consolidated:
            consolidated[symbol]["Quantity"] += order["Quantity"]
            consolidated[symbol]["Invested"] += order["Invested"]
        else:
            consolidated[symbol] = order.copy()

    return list(consolidated.values())


def _fallback_allocation_cheapest_symbol(
    remaining_capital: float,
    all_allocated_symbols: set[str],
    universe_symbols: list[str],
    latest_close: dict[str, float],
    rank_map: dict[str, str],
) -> list[dict]:
    """
    Fallback allocation strategy: Allocate remaining capital to cheapest unused symbol.
    
    Used when other allocation strategies have been exhausted and there's still
    capital remaining. Finds the cheapest stock from the universe that hasn't been
    allocated yet and buys as many shares as possible with the remaining capital.

    Parameters:
    - remaining_capital: Capital remaining to be allocated
    - all_allocated_symbols: Set of symbols that have already been allocated
    - universe_symbols: List of all symbols in the universe
    - latest_close: Dictionary mapping symbols to their latest prices
    - rank_map: Dictionary mapping symbols to their ranks

    Returns:
    - List of execution orders with Symbol, Rank, Action, Price, Quantity, Invested
    """
    if remaining_capital <= 0:
        return []

    # Find unused symbols that have price data
    unused_symbols = [
        s for s in universe_symbols 
        if s not in all_allocated_symbols and latest_close.get(s)
    ]
    
    if not unused_symbols:
        return []

    # Sort by price (cheapest first)
    fallback_universe = sorted(
        unused_symbols,
        key=lambda s: latest_close[s]
    )

    # Try to buy the cheapest unused symbol
    for sym in fallback_universe:
        price = latest_close[sym]
        qty = int(remaining_capital // price)
        
        if qty > 0:
            invested = qty * price
            return [
                {
                    "Symbol": sym,
                    "Rank": rank_map.get(sym, "N/A"),
                    "Action": "BUY",
                    "Price": round(price, 2),
                    "Quantity": qty,
                    "Invested": round(invested, 2),
                }
            ]

    return []


def plan_capital_addition(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    additional_capital: float,
    transaction_cost_pct: float = 0.001190,
) -> pd.DataFrame:
    """
    Generates a BUY-only execution plan to distribute additional capital efficiently.
    Uses a 3-step approach:
    1. Reserve transaction costs upfront
    2. Fill underweight holdings proportionally to target weight
    3. Distribute remaining capital equally across all stocks in portfolio
    4. Continue allocation rounds until remaining cash is minimal

    This approach handles both small and large capital amounts efficiently,
    minimizing leftover cash while maintaining approximate equal weighting.

    Parameters:
    - previous_holdings: List of dicts with keys 'symbol', 'quantity', 'buy_price'
    - price_data: Dict mapping symbols to price DataFrames
    - as_of_date: Date for which price is used
    - additional_capital: Total capital to be invested
    - transaction_cost_pct: Percentage of capital reserved for charges (default 0.119%)

    Returns:
    - DataFrame with BUY plan: Symbol, Action, Price, Quantity, Invested, Weight %
    """
    # Step 0: Build latest price lookup
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Step 1: Build current holdings with market value
    rows = []
    for h in previous_holdings:
        symbol = h["symbol"]
        qty = h["quantity"]
        price = latest_close.get(symbol)
        if price:
            rows.append(
                {"symbol": symbol, "price": price, "current_value": qty * price}
            )

    df_holdings = pd.DataFrame(rows)

    if not rows:
        return pd.DataFrame(
            data=[],
            columns=["Symbol", "Action", "Price", "Quantity", "Invested", "Weight %"]
        )

    # Step 2: Reserve transaction costs upfront
    transaction_cost_reserve = additional_capital * transaction_cost_pct
    investable_capital = additional_capital - transaction_cost_reserve

    # Step 3: Use improved top-up allocation logic (now without transaction cost handling)
    execution_data = _maximize_capital_deployment(
        df_holdings, investable_capital
    )

    # Step 4: Final formatting
    if execution_data:
        df_exec = pd.DataFrame(execution_data)
        total = df_exec["Invested"].sum()
        df_exec["Weight %"] = df_exec["Invested"] / total * 100

        return df_exec
    else:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )


def plan_portfolio_rebalance(
    held_stocks: list[str],
    new_entries: list[str],
    removed_stocks: list[str],
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    ranked_df: pd.DataFrame,
    transaction_cost_pct: float = 0.001190,
) -> pd.DataFrame:
    """
    Rebalance logic fully aligned with user's 5-point vision.
    - Fund new entries first to match equal-weight target
    - Allocate leftover capital to underweight holdings
    - Avoid trimming or over allocating
    - Apply 1-stock fallback for leftover capital
    """

    prev_df = pd.DataFrame(previous_holdings)

    if prev_df.empty or "symbol" not in prev_df.columns or "quantity" not in prev_df.columns:
        # When there are no previous holdings, treat as first-time investment
        # @todo: Use default capital of 1L (1,00,000) - can be fetched from broker later
        # symbols_list = ranked_df["symbol"].str.replace(".NS", "", regex=False).tolist()
        # return plan_equity_investment(symbols_list, price_data, as_of_date, 100000, ranked_df, transaction_cost_pct)
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
    ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))

    # Build latest_close from historical price data
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Map current prices to symbols, handling missing values
    prev_df["current_price"] = prev_df["symbol"].apply(lambda x: latest_close.get(x, 0))
    prev_df["current_value"] = prev_df["quantity"] * prev_df["current_price"]

    df_held = prev_df[prev_df["symbol"].isin(held_stocks)].copy()
    df_removed = prev_df[prev_df["symbol"].isin(removed_stocks)].copy()

    execution_data = []
    for _, row in df_removed.iterrows():
        execution_data.append(
            {
                "Symbol": row["symbol"],
                "Rank": rank_map.get(row["symbol"], "N/A"),
                "Action": "SELL",
                "Price": round(row["current_price"], 2),
                "Quantity": int(row["quantity"]),
                "Invested": round(row["current_value"], 2),
            }
        )

    total_sell_value = df_removed["current_value"].sum()
    estimated_cost = total_sell_value * 2 * transaction_cost_pct
    freed_capital = max(0, total_sell_value - estimated_cost)

    total_portfolio_value = df_held["current_value"].sum() + freed_capital
    target_weight_value = total_portfolio_value / (len(held_stocks) + len(new_entries))

    # Step 1: Allocate to new entries first
    used = 0
    new_entries_exec = []
    for sym in new_entries:
        price = latest_close.get(sym)
        if price is None:
            continue
        max_alloc = min(target_weight_value, freed_capital - used)
        qty = int(max_alloc // price)
        invested = qty * price
        if qty > 0 and used + invested <= freed_capital:
            new_entries_exec.append(
                {
                    "Symbol": sym,
                    "Rank": rank_map.get(sym, "N/A"),
                    "Action": "BUY",
                    "Price": round(price, 2),
                    "Quantity": qty,
                    "Invested": round(invested, 2),
                }
            )
            used += invested

    remaining = freed_capital - used

    # Step 2: Allocate remaining to underweight holdings
    held_targets = df_held.to_dict('records') if not df_held.empty else []
    held_exec = _fill_underweight_gaps_only(held_targets, remaining, target_weight_value, rank_map)
    used += sum(row["Invested"] for row in held_exec)
    remaining = freed_capital - used

    # Step 3: Fallback allocation via 1-share to cheapest unused symbol
    all_allocated = {r["Symbol"] for r in new_entries_exec + held_exec + execution_data}
    all_final = set(held_stocks + new_entries)
    
    fallback_exec = _fallback_allocation_cheapest_symbol(
        remaining, all_allocated, all_final, latest_close, rank_map
    )
    execution_data.extend(fallback_exec)

    execution_data.extend(new_entries_exec)
    execution_data.extend(held_exec)

    for _, row in df_held.iterrows():
        execution_data.append(
            {
                "Symbol": row["symbol"],
                "Rank": rank_map.get(row["symbol"], "N/A"),
                "Action": "HOLD",
                "Price": round(row["current_price"], 2),
                "Quantity": int(row["quantity"]),
                "Invested": round(row["current_value"], 2),
            }
        )

    df_exec = pd.DataFrame(execution_data)
    df_exec = df_exec.groupby(
        ["Symbol", "Rank", "Action", "Price"], as_index=False
    ).agg({"Quantity": "sum", "Invested": "sum"})
    total_value = df_exec.query("Action != 'SELL'")["Invested"].sum()
    df_exec.loc[:, "Weight %"] = df_exec.apply(
        lambda row: (
            round((row["Invested"] / total_value) * 100, 2)
            if row["Action"] != "SELL"
            else 0.0
        ),
        axis=1,
    )

    return df_exec.sort_values(by=["Action", "Symbol"], ascending=[False, True])


def plan_move_to_cash_equivalent(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    ranked_df: pd.DataFrame,
    cash_equivalent: str = "LIQUIDCASE.NS",
) -> pd.DataFrame:
    """
    Plans complete exit from all positions when market regime is weak and moves to cash equivalent.
    Sells all holdings and invests in the specified cash equivalent.

    Parameters:
    - previous_holdings: List of dicts with keys 'symbol', 'quantity', 'buy_price'
    - price_data: Dict mapping symbols to price DataFrames
    - as_of_date: Date for which price is used
    - ranked_df: DataFrame containing stock rankings (for rank mapping)
    - cash_equivalent: Symbol to use as cash equivalent (default: "LIQUIDCASE.NS")

    Returns:
    - DataFrame with SELL orders for all positions and BUY order for cash equivalent
    """
    if not previous_holdings:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    # Create rank mapping
    ranked_df = ranked_df.copy() if not ranked_df.empty else pd.DataFrame()
    if not ranked_df.empty:
        ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(
            ".NS", "", regex=False
        )
        ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
        ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
        rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))
    else:
        rank_map = {}

    # Get latest prices
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Filter out cash equivalent from current holdings if present
    non_cash_holdings = [
        h
        for h in previous_holdings
        if h["symbol"] != cash_equivalent.replace(".NS", "")
    ]

    # Step 1: Generate SELL orders for all non-cash positions
    execution_data = []
    total_value = 0

    for holding in non_cash_holdings:
        symbol = holding["symbol"]
        quantity = holding["quantity"]
        price = latest_close.get(symbol)

        if price and quantity > 0:
            current_value = quantity * price
            total_value += current_value

            execution_data.append(
                {
                    "Symbol": symbol,
                    "Rank": rank_map.get(symbol, "N/A"),
                    "Action": "SELL",
                    "Price": round(price, 2),
                    "Quantity": int(quantity),
                    "Invested": round(current_value, 2),
                    "Weight %": 0.0,
                }
            )

    # Step 2: Generate BUY order for cash equivalent
    # First check if we have price data for the cash equivalent
    cash_symbol_clean = cash_equivalent.replace(".NS", "")
    cash_price = latest_close.get(cash_symbol_clean)

    if cash_price and total_value > 0:
        # Assume 0.1% transaction cost
        transaction_cost = total_value * 0.001
        available_capital = total_value - transaction_cost

        # Calculate how many units we can buy
        qty = int(available_capital / cash_price)

        if qty > 0:
            invested = qty * cash_price

            execution_data.append(
                {
                    "Symbol": cash_symbol_clean,
                    "Rank": "N/A",
                    "Action": "BUY",
                    "Price": round(cash_price, 2),
                    "Quantity": qty,
                    "Invested": round(invested, 2),
                    "Weight %": 100.0,
                }
            )

    return (
        pd.DataFrame(execution_data)
        if execution_data
        else pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )
    )


def plan_capital_withdrawal(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    amount: float | None = None,
    percentage: float | None = None,
    full: bool = False,
    transaction_cost_pct: float = 0.001190,
) -> pd.DataFrame:
    """
    Plans the withdrawal of capital from the portfolio.

    Parameters:
    - previous_holdings: List of dicts with keys 'symbol', 'quantity', 'buy_price'
    - price_data: Dict mapping symbols to price DataFrames
    - as_of_date: Date for which price is used
    - amount: Specific amount to withdraw (₹)
    - percentage: Percentage of portfolio to withdraw (1-100)
    - full: If True, withdraws entire portfolio (overrides amount/percentage)
    - transaction_cost_pct: Percentage of transaction cost per trade

    Returns:
    - DataFrame with SELL orders for withdrawal
    """
    if not previous_holdings:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    # Get latest prices
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Calculate current portfolio value
    total_portfolio_value = sum(
        h["quantity"] * latest_close.get(h["symbol"], 0) for h in previous_holdings
    )

    # Determine withdrawal amount
    withdrawal_amount = 0
    if full:
        withdrawal_amount = total_portfolio_value
    elif percentage is not None:
        withdrawal_amount = total_portfolio_value * (percentage / 100)
    elif amount is not None:
        withdrawal_amount = amount
    else:
        return pd.DataFrame(
            data=[],
            columns=[
                "Symbol",
                "Rank",
                "Action",
                "Price",
                "Quantity",
                "Invested",
                "Weight %",
            ]
        )

    # For full withdrawal, sell everything
    if full:
        execution_data = []
        for holding in previous_holdings:
            symbol = holding["symbol"]
            quantity = holding["quantity"]
            price = latest_close.get(symbol)

            if price and quantity > 0:
                execution_data.append(
                    {
                        "Symbol": symbol,
                        "Rank": "N/A",
                        "Action": "SELL",
                        "Price": round(price, 2),
                        "Quantity": int(quantity),
                        "Invested": round(quantity * price, 2),
                        "Weight %": 0.0,
                    }
                )

        return pd.DataFrame(execution_data)

    # For partial withdrawal, calculate proportional quantities to sell
    withdrawal_ratio = withdrawal_amount / total_portfolio_value
    execution_data = []

    for holding in previous_holdings:
        symbol = holding["symbol"]
        quantity = holding["quantity"]
        price = latest_close.get(symbol)

        if price and quantity > 0:
            # Calculate sell quantity proportionally
            sell_qty = int(quantity * withdrawal_ratio)

            if sell_qty > 0:
                execution_data.append(
                    {
                        "Symbol": symbol,
                        "Rank": "N/A",
                        "Action": "SELL",
                        "Price": round(float(price), 2),
                        "Quantity": sell_qty,
                        "Invested": round(float(sell_qty * price), 2),
                        "Weight %": 0.0,
                    }
                )

    return pd.DataFrame(execution_data)
