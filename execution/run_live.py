from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices
from datetime import timedelta
from utils.date import get_last_trading_day
from logic.strategy import run_strategy
import pandas as pd

def run_live_strategy():
    """
    Executes the live rebalance logic for the current cycle.
    - Filters universe
    - Fetches price data
    - Runs strategy
    - Prints top 15 picks
    """
    
    print("🚀 Running live strategy...")

    # Step 1: Resolve current date
    as_of_date = pd.to_datetime(get_last_trading_day())
    print(f"📆 Last Trading Day: {as_of_date.date()}")

    # Step 2: Load and filter universe
    universe = get_universe_symbols("nifty500")
    filtered = apply_universe_filters(universe)
    symbols = [f"{s}.NS" for s in filtered] + ["^NSEI"]

    # Step 3: Fetch price data (last 400 days)
    start = (as_of_date - timedelta(days=400)).strftime("%Y-%m-%d")
    end = as_of_date.strftime("%Y-%m-%d")
    price_data = download_and_cache_prices(symbols, start=start, end=end)

    # Step 4: Run strategy
    portfolio = run_strategy(price_data, as_of_date)

    # Step 5: Print output
    if portfolio.empty:
        print("💤 Market weak. Please cut all the positions and invest in LIQUIDBEES this week.")
    else:
        print("✅ Final Portfolio (Top 15):")
        print(portfolio[["symbol", "total_rank"]].reset_index(drop=True))
