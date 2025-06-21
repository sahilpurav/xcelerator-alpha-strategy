import pandas as pd
import os
from config import Config
from utils.notification import send_whatsapp_message

def display_portfolio_table(data: list[dict], label_map: dict, tsv: bool = False):
    """
    Prints a formatted table (human-readable or TSV for Google Sheets).
    :param data: List of dicts like [{'symbol': ..., 'quantity': ..., 'buy_price': ..., 'last_price: ...}]
    :param label_map: Dict like {'symbol': ('Symbol', 12), 'quantity': ('Quantity', 10)}
    :param tsv: If True, output tab-separated values (good for Google Sheets)
    """
    if not data:
        print("🚫 No active CNC entries.")
        return

    # Calculate current_value for each row (for summary only)
    for row in data:
        row['current_value'] = row.get('quantity', 0) * row.get('last_price', 0)

    # Extract header and rows
    if tsv:
        # For TSV, exclude last_price from the labels
        tsv_label_map = {k: v for k, v in label_map.items() if k != 'last_price'}
        headers = [label for _, (label, _) in tsv_label_map.items()]
        keys = list(tsv_label_map.keys())
        print("\t".join(headers))
        for row in data:
            print("\t".join(str(row.get(key, "")) for key in keys))
    else:
        headers = [label for _, (label, _) in label_map.items()]
        keys = list(label_map.keys())
        header = "".join(f"{label:<{width}}" for _, (label, width) in label_map.items())
        print(header)
        print("-" * len(header))
        for row in data:
            line = "".join(
                f"{str(row.get(key, '')):<{width}}" for key, (_, width) in label_map.items()
            )
            print(line)

    # Calculate and print investment summary
    total_invested = sum(row.get('quantity', 0) * row.get('buy_price', 0) for row in data)
    total_current = sum(row.get('current_value', 0) for row in data)

    print("\n💼 Investment Summary")
    print(f"📌 Total Invested Value : ₹{total_invested:,.2f}")
    print(f"📌 Total Current Value  : ₹{total_current:,.2f}")

def display_execution_plan(exec_df: pd.DataFrame, type: str):
    """
    Displays the execution plan in a user-friendly format.
    
    Args:
        exec_df (pd.DataFrame): DataFrame containing execution plan details
        type (str): Type of execution plan - 'rebalance', 'initial', or 'top-up'
    """
    title_map = {
        'rebalance': '🔄 Portfolio Rebalancing Plan',
        'initial': '🎯 Initial Investment Plan',
        'top-up': '📈 Top-up Investment Plan'
    }
    title = title_map.get(type, 'Execution Plan')

    print("-" * 65)
    print(f"{title}")
    print("-" * 65)
    preferred_cols = ["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"]
    available_cols = [col for col in preferred_cols if col in exec_df.columns]
    
    # Filter out INFO rows for calculations
    trade_df = exec_df[exec_df["Action"].isin(["BUY", "SELL", "HOLD"])]
    
    # Calculate basic amounts
    buy_amount = trade_df[trade_df["Action"] == "BUY"]["Invested"].sum()
    sell_amount = trade_df[trade_df["Action"] == "SELL"]["Invested"].sum()
    hold_amount = trade_df[trade_df["Action"] == "HOLD"]["Invested"].sum()
    
    # Print the execution plan
    print(exec_df[available_cols].to_string(index=False))
    
    # Print type-specific summaries
    print("-" * 65)
    print("💼 Investment Summary")
    print("-" * 65)
    
    if type == 'rebalance':
        portfolio_value_before = hold_amount + sell_amount
        portfolio_value_after = hold_amount + buy_amount
        print(f"📊 Portfolio Value (Before) : ₹{portfolio_value_before:,.2f}")
        print(f"📈 Portfolio Value (After)  : ₹{portfolio_value_after:,.2f}")
        
    elif type == 'initial':
        print(f"🎯 Total Portfolio Value    : ₹{buy_amount:,.2f}")
        
    elif type == 'top-up':
        print(f"💰 Total Top-up Allocation  : ₹{buy_amount:,.2f}")

    if Config.ENABLE_TWILIO_WHATSAPP:
        print("📱 Sending notification on WhatsApp...")
        send_whatsapp_message(exec_df)
