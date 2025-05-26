import pandas as pd
import typer
from broker.zerodha import ZerodhaBroker

def execute_orders(exec_df: pd.DataFrame, broker: ZerodhaBroker, dry_run: bool = False):
    """
    Executes the given execution plan using the broker API.
    SELLs are executed first, followed by BUYs.
    """

    # Ask for confirmation
    if not typer.confirm("⚠️ Do you want to proceed with live order execution?"):
        print("❎ Skipped live order execution.")
        return
    
    print("\n📡 Placing live orders via broker...")

    for action in ["SELL", "BUY"]:
        df_action = exec_df.query(f"Action == '{action}'")
        for _, row in df_action.iterrows():
            symbol = row["Symbol"]
            quantity = int(row["Quantity"])
            if quantity <= 0:
                continue

            print(f"{'🔻' if action == 'SELL' else '🔺'} {action} {symbol}: Qty = {quantity}")
            if not dry_run:
                try:
                    broker.place_market_order(symbol, quantity, transaction_type=action)
                except Exception as e:
                    print(f"❌ Failed to {action} {symbol}: {e}")
