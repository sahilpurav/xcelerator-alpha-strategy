import pandas as pd
import math

# Capital Allocation Strategy Functions:
# _fill_underweight_gaps_only() - Conservative: Fill gaps only (for rebalance)
# _maximize_capital_deployment() - Aggressive: 3-step deployment (for top-ups)
    
def plan_initial_investment(
    symbols: list[str],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    total_capital: float,
    ranked_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generates an execution plan for first-time investment in selected stocks.
    Allocates total capital equally across the given symbols and computes
    quantities, investment amounts, and weights based on latest prices.

    Parameters:
    - symbols: List of selected stock symbols (e.g., ['TCS', 'INFY'])
    - price_data: Dictionary mapping symbols to their historical price DataFrames
    - as_of_date: Timestamp representing the date for which prices are used
    - total_capital: Total capital to be deployed
    - ranked_df: DataFrame containing stock rankings, including 'total_rank'

    Returns:
    - DataFrame with execution plan containing columns:
      ['Symbol', 'Rank', 'Action', 'Price', 'Quantity', 'Invested', 'Weight %']
    """

    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Two-pass allocation strategy to maximize capital deployment
    per_stock_alloc = total_capital / len(symbols) if symbols else 0
    
    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
    ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))

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

    # Second pass: Redistribute total capital equally among purchasable stocks only
    execution_data = []
    if purchasable_stocks:
        adjusted_per_stock_alloc = total_capital / len(purchasable_stocks)
        
        for sym_clean in purchasable_stocks:
            price = latest_close.get(sym_clean)
            
            if not price or price == 0:
                continue

            qty = math.floor(adjusted_per_stock_alloc / price)
            if qty == 0:
                continue

            invested = round(qty * price, 2)

            execution_data.append({
                "Symbol": sym_clean,
                "Rank": rank_map.get(sym_clean, "N/A"),
                "Action": "BUY",
                "Price": round(price, 2),
                "Quantity": qty,
                "Invested": invested,
            })

    if execution_data:
        df_exec = pd.DataFrame(execution_data)
        total_value = df_exec["Invested"].sum()
        df_exec["Weight %"] = df_exec["Invested"] / total_value * 100
    else:
        df_exec = pd.DataFrame(columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"])

    return df_exec

def _fill_underweight_gaps_only(
    targets: list[dict],
    total_capital: float,
    transaction_cost_pct: float = 0.001190
) -> list[dict]:
    """
    Conservative allocation strategy: Only fills gaps for underweight holdings.
    
    Used by rebalance logic where we want targeted, controlled allocation
    without over-deploying capital. This function stops after filling
    underweight gaps and doesn't attempt to maximize capital deployment.

    Strategy:
    - Only targets underweight holdings (current_value < target_weight)
    - Distributes capital proportionally to the gap size
    - Conservative approach - no aggressive deployment
    - Transaction costs are accounted for in quantity calculation

    Parameters:
    - targets: List of dicts with keys 'symbol', 'price', 'current_value'
    - total_capital: Total capital available for allocation
    - transaction_cost_pct: Percentage of transaction cost per trade (default 0.119%)

    Returns:
    - List of dicts with keys: Symbol, Action, Price, Quantity, Invested
    """
    import pandas as pd

    # Handle empty targets list
    if not targets:
        return []
    
    df = pd.DataFrame(targets)
    
    # Validate required columns exist
    required_cols = ['symbol', 'price', 'current_value']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return []
    
    total_value = df["current_value"].sum() + total_capital
    target_weight = total_value / len(df)

    # Filter only underweight holdings
    df = df[df["current_value"] < target_weight].copy()
    df["gap"] = target_weight - df["current_value"]
    total_gap = df["gap"].sum()

    execution_data = []
    capital_used = 0

    for _, row in df.iterrows():
        alloc = total_capital * (row["gap"] / total_gap) if total_gap > 0 else 0
        remaining_budget = total_capital - capital_used
        
        # Account for transaction cost in price calculation
        effective_price = row["price"] * (1 + transaction_cost_pct)
        est_qty = min(int(alloc // effective_price), int(remaining_budget // effective_price))
        est_invested = est_qty * row["price"]  # Original price for actual investment amount

        # Only allocate if quantity is positive
        if est_qty > 0:
            execution_data.append({
                "Symbol": row["symbol"],
                "Action": "BUY",
                "Price": round(row["price"], 2),
                "Quantity": est_qty,
                "Invested": round(est_invested, 2)
            })
            capital_used += est_invested * (1 + transaction_cost_pct)  # Include transaction cost in used capital

    return execution_data


def _maximize_capital_deployment(
    df_holdings: pd.DataFrame,
    additional_capital: float,
    transaction_cost_pct: float = 0.001190
) -> list[dict]:
    """
    Aggressive deployment strategy: 3-step approach to maximize capital utilization.
    
    Step 1: Fill underweight holdings proportionally
    Step 2: Equally distribute remaining capital across all stocks in portfolio
    Step 3: Continue until remaining cash is minimal (< capital * transaction_cost_pct)
    
    Used by top-up logic where we want to deploy as much capital as possible
    while maintaining approximate equal weighting.
    
    Parameters:
    - df_holdings: DataFrame with columns 'symbol', 'price', 'current_value'
    - additional_capital: Total capital to be invested
    - transaction_cost_pct: Transaction cost percentage
    
    Returns:
    - List of execution orders with Symbol, Action, Price, Quantity, Invested
    """
    import pandas as pd
    
    if df_holdings.empty:
        return []
    
    # Step 1: Fill underweight holdings (existing logic)
    total_value = df_holdings["current_value"].sum() + additional_capital
    target_weight = total_value / len(df_holdings)
    
    underweight_df = df_holdings[df_holdings["current_value"] < target_weight].copy()
    underweight_df["gap"] = target_weight - underweight_df["current_value"]
    total_gap = underweight_df["gap"].sum()
    
    execution_data = []
    remaining_capital = additional_capital
    
    # Allocate to underweight holdings first
    for _, row in underweight_df.iterrows():
        if remaining_capital <= 0:
            break
            
        alloc = additional_capital * (row["gap"] / total_gap) if total_gap > 0 else 0
        effective_price = row["price"] * (1 + transaction_cost_pct)
        est_qty = min(int(alloc // effective_price), int(remaining_capital // effective_price))
        
        if est_qty > 0:
            est_invested = est_qty * row["price"]
            total_cost = est_invested * (1 + transaction_cost_pct)
            
            execution_data.append({
                "Symbol": row["symbol"],
                "Action": "BUY",
                "Price": round(row["price"], 2),
                "Quantity": est_qty,
                "Invested": round(est_invested, 2)
            })
            remaining_capital -= total_cost
    
    # Step 2 & 3: Distribute remaining capital equally across all stocks
    # Continue until remaining capital is close to transaction cost buffer
    min_remaining_threshold = additional_capital * transaction_cost_pct
    
    while remaining_capital > min_remaining_threshold:
        num_stocks = len(df_holdings)
        per_stock_allocation = remaining_capital / num_stocks
        
        # Track if we made any allocation in this round
        allocated_this_round = False
        round_cost = 0
        round_orders = []
        
        # Try to allocate equally across all stocks
        for _, row in df_holdings.iterrows():
            effective_price = row["price"] * (1 + transaction_cost_pct)
            
            # Calculate quantity based on per-stock allocation, but at least 1 share
            qty_from_allocation = int(per_stock_allocation // effective_price)
            qty = max(1, qty_from_allocation) if per_stock_allocation >= effective_price else 0
            
            if qty > 0 and round_cost + (qty * effective_price) <= remaining_capital:
                invested = qty * row["price"]
                total_cost = invested * (1 + transaction_cost_pct)
                
                round_orders.append({
                    "Symbol": row["symbol"],
                    "Action": "BUY", 
                    "Price": round(row["price"], 2),
                    "Quantity": qty,
                    "Invested": round(invested, 2)
                })
                round_cost += total_cost
                allocated_this_round = True
        
        # If we couldn't allocate to any stock this round, break to avoid infinite loop
        if not allocated_this_round:
            break
            
        # Add this round's orders to execution data and update remaining capital
        execution_data.extend(round_orders)
        remaining_capital -= round_cost
        
        # If remaining capital is small enough, break
        if remaining_capital <= min_remaining_threshold:
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


def plan_top_up_investment(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    additional_capital: float,
    transaction_cost_pct: float = 0.001190
) -> pd.DataFrame:
    """
    Generates a BUY-only execution plan to distribute additional capital efficiently.
    Uses a 3-step approach:
    1. Fill underweight holdings proportionally to target weight
    2. Distribute remaining capital equally across all stocks in portfolio
    3. Continue allocation rounds until remaining cash is minimal (< capital * transaction_cost_pct)
    
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
            rows.append({"symbol": symbol, "price": price, "current_value": qty * price})

    df_holdings = pd.DataFrame(rows)
    
    if not rows:
        return pd.DataFrame(columns=["Symbol", "Action", "Price", "Quantity", "Invested", "Weight %"])

    # Step 2: Use improved top-up allocation logic
    execution_data = _maximize_capital_deployment(
        df_holdings,
        additional_capital,
        transaction_cost_pct
    )

    # Step 3: Final formatting
    if execution_data:
        df_exec = pd.DataFrame(execution_data)
        total = df_exec["Invested"].sum()
        df_exec["Weight %"] = df_exec["Invested"] / total * 100
        
        return df_exec
    else:
        return pd.DataFrame(columns=["Symbol", "Action", "Price", "Quantity", "Invested", "Weight %"])

def plan_rebalance_investment(
    held_stocks: list[str],
    new_entries: list[str],
    removed_stocks: list[str],
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    ranked_df: pd.DataFrame,
    transaction_cost_pct: float = 0.001190
) -> pd.DataFrame:
    """
    Rebalance logic fully aligned with user's 5-point vision.
    - Fund new entries first to match equal-weight target
    - Allocate leftover capital to underweight holdings
    - Avoid trimming or overallocating
    - Apply 1-stock fallback for leftover capital
    """
    import pandas as pd

    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
    ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))

    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    prev_df = pd.DataFrame(previous_holdings)
    
    if prev_df.empty:
        return pd.DataFrame(columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested"])
    
    if "symbol" not in prev_df.columns or "quantity" not in prev_df.columns:
        return pd.DataFrame(columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested"])
    
    prev_df["current_price"] = prev_df["symbol"].map(latest_close)
    prev_df["current_value"] = prev_df["quantity"] * prev_df["current_price"]

    df_held = prev_df[prev_df["symbol"].isin(held_stocks)].copy()
    df_removed = prev_df[prev_df["symbol"].isin(removed_stocks)].copy()

    execution_data = []
    for _, row in df_removed.iterrows():
        execution_data.append({
            "Symbol": row["symbol"],
            "Rank": rank_map.get(row["symbol"], "N/A"),
            "Action": "SELL",
            "Price": round(row["current_price"], 2),
            "Quantity": int(row["quantity"]),
            "Invested": round(row["current_value"], 2),
        })

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
            new_entries_exec.append({
                "Symbol": sym,
                "Rank": rank_map.get(sym, "N/A"),
                "Action": "BUY",
                "Price": round(price, 2),
                "Quantity": qty,
                "Invested": round(invested, 2)
            })
            used += invested

    remaining = freed_capital - used

    # Step 2: Allocate remaining to underweight holdings
    held_targets = []
    if not df_held.empty and "current_value" in df_held.columns and "current_price" in df_held.columns:
        for _, row in df_held.iterrows():
            if row["current_value"] < target_weight_value:
                held_targets.append({
                    "symbol": row["symbol"],
                    "price": row["current_price"],
                    "current_value": row["current_value"]
                })

    held_exec = _fill_underweight_gaps_only(held_targets, remaining)
    used += sum(row["Invested"] for row in held_exec)
    remaining = freed_capital - used

    # Step 3: Fallback allocation via 1-share to cheapest unused symbol
    all_allocated = {r["Symbol"] for r in new_entries_exec + held_exec + execution_data}
    all_final = set(held_stocks + new_entries)
    fallback_universe = sorted(
        [s for s in all_final if s not in all_allocated and latest_close.get(s)],
        key=lambda s: latest_close[s]
    )
    for sym in fallback_universe:
        price = latest_close[sym]
        qty = int(remaining // price)
        if qty > 0:
            invested = qty * price
            execution_data.append({
                "Symbol": sym,
                "Rank": rank_map.get(sym, "N/A"),
                "Action": "BUY",
                "Price": round(price, 2),
                "Quantity": qty,
                "Invested": round(invested, 2)
            })
            break

    execution_data.extend(new_entries_exec)
    execution_data.extend(held_exec)

    for _, row in df_held.iterrows():
        execution_data.append({
            "Symbol": row["symbol"],
            "Rank": rank_map.get(row["symbol"], "N/A"),
            "Action": "HOLD",
            "Price": round(row["current_price"], 2),
            "Quantity": int(row["quantity"]),
            "Invested": round(row["current_value"], 2)
        })

    df_exec = pd.DataFrame(execution_data)
    df_exec = df_exec.groupby(["Symbol", "Rank", "Action", "Price"], as_index=False).agg({
        "Quantity": "sum",
        "Invested": "sum"
    })
    total_value = df_exec.query("Action != 'SELL'")["Invested"].sum()
    df_exec["Weight %"] = df_exec.apply(
        lambda row: round((row["Invested"] / total_value) * 100, 2) if row["Action"] != "SELL" else 0.0,
        axis=1
    )

    return df_exec.sort_values(by=["Action", "Symbol"], ascending=[False, True])

def plan_exit_all_positions(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    ranked_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Plans complete exit from all positions when market regime is weak.
    Sells all holdings and goes to cash.
    
    Parameters:
    - previous_holdings: List of dicts with keys 'symbol', 'quantity', 'buy_price'
    - price_data: Dict mapping symbols to price DataFrames
    - as_of_date: Date for which price is used
    - ranked_df: DataFrame containing stock rankings (for rank mapping)
    
    Returns:
    - DataFrame with SELL orders for all positions
    """
    if not previous_holdings:
        return pd.DataFrame(columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"])
    
    # Create rank mapping
    ranked_df = ranked_df.copy() if not ranked_df.empty else pd.DataFrame()
    if not ranked_df.empty:
        ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
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
    
    execution_data = []
    for holding in previous_holdings:
        symbol = holding["symbol"]
        quantity = holding["quantity"]
        price = latest_close.get(symbol)
        
        if price and quantity > 0:
            execution_data.append({
                "Symbol": symbol,
                "Rank": rank_map.get(symbol, "N/A"),
                "Action": "SELL",
                "Price": round(price, 2),
                "Quantity": int(quantity),
                "Invested": round(quantity * price, 2),
                "Weight %": 0.0
            })
    
    return pd.DataFrame(execution_data) if execution_data else pd.DataFrame(columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"])