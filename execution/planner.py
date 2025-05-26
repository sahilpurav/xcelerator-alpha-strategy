import pandas as pd
import math
    

def generate_execution_plan(
    held_stocks: list[str],
    new_entries: list[str],
    removed_stocks: list[str],
    previous_holdings: list[dict],
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    additional_capital: float,
    ranked_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Generate final execution plan (HOLD, BUY, SELL) with quantities based on:
    - existing holdings
    - new entries
    - capital freed from sells
    - optional fresh capital
    """
    # Step 1: Build lookup for current prices
    latest_close = {
        symbol.replace(".NS", ""): df.loc[as_of_date, "Close"]
        for symbol, df in price_data.items()
        if as_of_date in df.index
    }

    # Step 2: Create DF from previous holdings
    prev_df = pd.DataFrame(previous_holdings)
    prev_df["current_price"] = prev_df["symbol"].map(latest_close)
    prev_df["effective_price"] = prev_df.apply(
        lambda row: row["buy_price"] if pd.notna(row.get("buy_price")) and row["buy_price"] > 0 else row["current_price"],
        axis=1
    )
    prev_df["current_value"] = prev_df["quantity"] * prev_df["effective_price"]

    # Step 3: Split into held and removed
    df_held = prev_df[prev_df["symbol"].isin(held_stocks)].copy()
    df_removed = prev_df[prev_df["symbol"].isin(removed_stocks)].copy()

    # Step 4: Capital freed from sells
    freed_capital = df_removed["current_value"].sum()
    total_allocatable = freed_capital + additional_capital

    # Step 5: Equal allocation to new entries
    per_stock_alloc = total_allocatable / len(new_entries) if new_entries else 0

    execution_data = []

    # Step 6: Create a rank map if available
    ranked_df = ranked_df.copy()
    ranked_df["symbol_clean"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    rank_map = dict(zip(ranked_df["symbol_clean"], ranked_df["rank"]))

    # Step 7: Add HOLDs
    for _, row in df_held.iterrows():
        invested = round(row["quantity"] * row["current_price"], 2)
        execution_data.append({
            "Symbol": row["symbol"],
            "Rank": rank_map.get(row["symbol"], "N/A"),
            "Action": "HOLD",
            "Price": round(row["current_price"], 2),
            "Quantity": int(row["quantity"]),
            "Invested": invested,
        })

    # Step 8: Add BUYs
    for symbol in new_entries:
        price = latest_close.get(symbol)
        if not price or price == 0:
            continue
        qty = math.floor(per_stock_alloc / price)
        invested = round(qty * price, 2)
        execution_data.append({
            "Symbol": symbol,
            "Rank": rank_map.get(symbol, "N/A"),
            "Action": "BUY",
            "Price": round(price, 2),
            "Quantity": qty,
            "Invested": invested,
        })

    # Step 9: Add SELLs
    for _, row in df_removed.iterrows():
        execution_data.append({
            "Symbol": row["symbol"],
            "Rank": rank_map.get(row["symbol"], "N/A"),
            "Action": "SELL",
            "Price": round(row["current_price"], 2),
            "Quantity": int(row["quantity"]),
            "Invested": round(row["current_value"], 2),
        })

    df_exec = pd.DataFrame(execution_data)
    total_value = df_exec.query("Action != 'SELL'")["Invested"].sum()
    df_exec["Weight %"] = df_exec.apply(
        lambda row: round((row["Invested"] / total_value) * 100, 2) if row["Action"] != "SELL" else 0.0,
        axis=1
    )

    return df_exec.sort_values(by=["Action", "Symbol"], ascending=[False, True])
