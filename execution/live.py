from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices
from datetime import timedelta
from utils.date import get_last_trading_day
from logic.strategy import get_ranked_stocks, generate_band_adjusted_portfolio
from execution.planner import generate_execution_plan
import pandas as pd
from broker.zerodha import ZerodhaBroker

def _get_filtered_universe() -> list[str]:
    """
    Fetches the universe of symbols, applies filters, and returns the filtered list.
    """
    universe = get_universe_symbols("nifty500")
    return apply_universe_filters(universe)

def _get_latest_prices(symbols: list[str], as_of_date: pd.Timestamp) -> dict:
    """
    Fetches stock prices for the given symbols from the start of the year to the as_of_date.
    """
    start = (as_of_date - timedelta(days=400)).strftime("%Y-%m-%d")
    end = as_of_date.strftime("%Y-%m-%d")
    return download_and_cache_prices(symbols, start=start, end=end)

def _get_previous_holdings(broker: ZerodhaBroker) -> list[dict]:
    """
    Fetches previous holdings from the broker and formats them.
    """
    holdings = broker.get_holdings()
    return [
        {
            "symbol": h["tradingsymbol"].replace(".NS", ""),
            "quantity": h["quantity"],
            "buy_price": h["average_price"]
        }
        for h in holdings if h["quantity"] > 0
    ]

def run_live_strategy(top_n: int = 15, band: int = 5, additional_capital: float = 0.0):
    """
    Executes the live rebalance logic for the current cycle.
    - Filters universe
    - Fetches price data
    - Ranks stocks
    - Generates portfolio based on band logic
    - Displays execution plan
    - Optionally places orders via broker
    """
    
    print("\n🚀 Running live strategy...")

    # Step 1: Resolve date
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"📆 Last Trading Day: {as_of_date.date()}")

    # Step 2: Universe + Prices
    filtered = _get_filtered_universe()
    symbols = [f"{s}.NS" for s in filtered] + ["^NSEI"]
    price_data = _get_latest_prices(symbols, as_of_date)

    # Step 4: Get latest ranking
    ranked_stocks_df = get_ranked_stocks(price_data, as_of_date)
    top_n_df = ranked_stocks_df.nsmallest(top_n, "total_rank")
    if top_n_df.empty:
        print("💤 Market weak or no opportunities. Strategy will stay in cash.")
        return

    # Step 5: Get live holdings from broker
    broker = ZerodhaBroker()
    previous_holdings = _get_previous_holdings(broker)
    held_symbols = [h["symbol"] for h in previous_holdings]

    # Step 6: Apply band logic
    held, new_entries, removed, _ = generate_band_adjusted_portfolio(
        ranked_stocks_df, held_symbols, top_n=top_n, band=band
    )

    # Step 7: Generate execution plan
    exec_df = generate_execution_plan(
        held, new_entries, removed, previous_holdings,
        price_data, as_of_date, additional_capital, ranked_stocks_df
    )

    # Step 8: Display
    print("\n📦 Final Execution Plan")
    display_cols = ["Symbol", "Rank", "Action", "Price", "Quantity", "Invested", "Weight %"]
    print(exec_df[display_cols].to_string(index=False))

    # Step 9: Place orders (SELL first, then BUY)
    # for _, row in exec_df.query("Action == 'SELL'").iterrows():
    #     broker.place_market_order(row["Symbol"], row["Quantity"], transaction_type="SELL")

    # for _, row in exec_df.query("Action == 'BUY'").iterrows():
    #     broker.place_market_order(row["Symbol"], row["Quantity"], transaction_type="BUY")

