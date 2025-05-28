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

def _allocate_to_underweight_targets(
    targets: list[dict],
    total_capital: float
) -> list[dict]:
    """
    Allocate capital proportionally to a list of underweight targets.
    Each target must have: symbol, current_value, price
    """
    df = pd.DataFrame(targets)
    total_value = df["current_value"].sum() + total_capital
    target_weight = total_value / len(df)

    df = df[df["current_value"] < target_weight].copy()
    df["gap"] = target_weight - df["current_value"]
    total_gap = df["gap"].sum()

    execution_data = []
    for _, row in df.iterrows():
        alloc = total_capital * (row["gap"] / total_gap)
        qty = math.floor(alloc / row["price"])
        if qty == 0:
            continue
        invested = round(qty * row["price"], 2)
        execution_data.append({
            "Symbol": row["symbol"],
            "Action": "BUY",
            "Price": round(row["price"], 2),
            "Quantity": qty,
            "Invested": invested
        })

    return execution_data


def plan_top_up_investment(
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    additional_capital: float,
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

    Returns:
    - DataFrame with BUY plan: Symbol, Action, Price, Quantity, Invested, Weight %
    """
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    rows = []
    for h in previous_holdings:
        symbol = h["symbol"]
        qty = h["quantity"]
        price = latest_close.get(symbol)
        if price:
            rows.append({"symbol": symbol, "price": price, "current_value": qty * price})

    # Step 1: Proportional top-up
    execution_data = _allocate_to_underweight_targets(rows, additional_capital)
    allocated = sum(e["Invested"] for e in execution_data)
    remaining = additional_capital - allocated

    # Step 2: Try to reinvest residual capital in 1-share lots
    df_holdings = pd.DataFrame(rows)
    already_topped_up = {e["Symbol"] for e in execution_data}
    eligible = df_holdings[~df_holdings["symbol"].isin(already_topped_up)].copy()

    # Sort by price (lowest first to maximize usage)
    eligible = eligible.sort_values(by="price")

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

    # Final formatting
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
    ranked_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate execution plan for rebalance.
    - Sells removed stocks
    - Buys new entries and tops up underweight HOLDs using freed capital
    - Uses normalized rank (1, 2, ..., N), N/A for unranked (e.g., ASM)
    """
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

    if prev_df["current_price"].isnull().any():
        missing = prev_df[prev_df["current_price"].isnull()]["symbol"].tolist()
        print(f"⚠️ Warning: Missing current price for: {missing}")

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

    freed_capital = df_removed["current_value"].sum()

    max_new = len(removed_stocks)
    if len(new_entries) > max_new:
        new_entries = sorted(
            new_entries,
            key=lambda s: rank_map.get(s, float("inf"))
        )[:max_new]

    final_symbols = list(set(held_stocks + new_entries))
    df_final = pd.DataFrame([
        {
            "symbol": sym,
            "price": latest_close.get(sym),
            "current_value": df_held.loc[df_held["symbol"] == sym, "current_value"].values[0]
            if sym in df_held["symbol"].values else 0
        }
        for sym in final_symbols if latest_close.get(sym) is not None
    ])

    buy_entries = _allocate_to_underweight_targets(
        targets=df_final.to_dict("records"),
        total_capital=freed_capital
    )

    for row in buy_entries:
        row["Rank"] = rank_map.get(row["Symbol"], "N/A")
        execution_data.append(row)

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
    total_value = df_exec.query("Action != 'SELL'")["Invested"].sum()
    df_exec["Weight %"] = df_exec.apply(
        lambda row: round((row["Invested"] / total_value) * 100, 2) if row["Action"] != "SELL" else 0.0,
        axis=1
    )

    return df_exec.sort_values(by=["Action", "Symbol"], ascending=[False, True])