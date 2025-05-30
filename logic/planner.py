import pandas as pd
import math
    
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

    per_stock_alloc = total_capital / len(symbols) if symbols else 0
    execution_data = []

    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    ranked_df = ranked_df.sort_values("total_rank").reset_index(drop=True)
    ranked_df["normalized_rank"] = range(1, len(ranked_df) + 1)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["normalized_rank"]))

    for symbol in symbols:
        sym_clean = symbol.replace(".NS", "")
        price = latest_close.get(sym_clean)

        if not price or price == 0:
            continue

        qty = math.floor(per_stock_alloc / price)
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

def _allocate_topups_to_underweight_holdings(
    targets: list[dict],
    total_capital: float
) -> list[dict]:
    """
    Allocates capital to underweight targets based on their current value
    and the target weight derived from total capital.

    This function assumes:
    - All targets are underweight (current_value < target_weight)
    - No trimming is allowed
    - Capital should be distributed proportionally to the gap
    - Quantity is floored to avoid overshooting the budget

    Parameters:
    - targets: List of dicts with keys 'symbol', 'price', 'current_value'
    - total_capital: Total capital available for allocation

    Returns:
    - List of dicts with keys: Symbol, Action, Price, Quantity, Invested
    """
    import pandas as pd

    df = pd.DataFrame(targets)
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
        est_qty = int(alloc // row["price"])
        est_invested = est_qty * row["price"]

        # Only allocate if quantity is positive and we remain within budget
        if est_qty > 0 and (capital_used + est_invested) <= total_capital:
            execution_data.append({
                "Symbol": row["symbol"],
                "Action": "BUY",
                "Price": round(row["price"], 2),
                "Quantity": est_qty,
                "Invested": round(est_invested, 2)
            })
            capital_used += est_invested

    return execution_data


def plan_top_up_investment(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    additional_capital: float,
    transaction_cost_pct: float = 0.002  # 0.20% buffer on top-up capital
) -> pd.DataFrame:
    """
    Generates a BUY-only execution plan to distribute additional capital
    across underweight holdings to restore approximate equal weight.
    Also allocates leftover capital equally by buying 1 share lots of eligible stocks.
    
    Parameters:
    - previous_holdings: List of dicts with keys 'symbol', 'quantity', 'buy_price'
    - price_data: Dict mapping symbols to price DataFrames
    - as_of_date: Date for which price is used
    - additional_capital: Total capital to be invested
    - transaction_cost_pct: Percentage of capital reserved for charges (default 0.20%)

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

    # Step 2: Apply transaction buffer on additional capital
    estimated_cost = additional_capital * transaction_cost_pct
    usable_capital = max(0, additional_capital - estimated_cost)
    print(f"🔒 Reserved ₹{estimated_cost:,.2f} ({transaction_cost_pct*100:.2f}%) as buffer for transaction costs.")

    # Step 3: Allocate to underweight targets
    execution_data = _allocate_topups_to_underweight_holdings(rows, usable_capital)
    allocated = sum(e["Invested"] for e in execution_data)
    remaining = additional_capital - allocated

    # Step 4: Reinvest residual capital in 1-share lots
    already_topped_up = {e["Symbol"] for e in execution_data}
    eligible = df_holdings[~df_holdings["symbol"].isin(already_topped_up)].copy()
    eligible = eligible.sort_values(by="price")  # Cheapest first

    for _, row in eligible.iterrows():
        if remaining >= row["price"]:
            qty = 1
            invested = round(row["price"] * qty, 2)
            execution_data.append({
                "Symbol": row["symbol"],
                "Action": "BUY",
                "Price": round(row["price"], 2),
                "Quantity": qty,
                "Invested": invested
            })
            remaining -= invested

    # Step 5: Final formatting
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
    transaction_cost_pct: float = 0.002
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
    print(f"\U0001f512 Reserved ₹{estimated_cost:,.2f} ({transaction_cost_pct*100:.2f}%) as buffer for transaction costs.")

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
    for _, row in df_held.iterrows():
        if row["current_value"] < target_weight_value:
            held_targets.append({
                "symbol": row["symbol"],
                "price": row["current_price"],
                "current_value": row["current_value"]
            })

    held_exec = _allocate_topups_to_underweight_holdings(held_targets, remaining)
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