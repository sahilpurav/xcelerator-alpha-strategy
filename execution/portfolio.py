import os
from datetime import datetime

import pandas as pd
import typer

from broker.zerodha import ZerodhaBroker
from data.price_fetcher import download_and_cache_prices, is_cache_stale_or_missing
from data.universe_fetcher import get_universe_symbols
from logic.display import display_portfolio_table
from utils.cache import save_to_file
from utils.market import is_market_strong


def run_holdings_display(tsv: bool = False):
    """Display current holdings and their details."""
    broker = ZerodhaBroker()
    portfolio = broker.get_holdings()

    display_portfolio_table(
        portfolio,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
            "last_price": ("Close Price", 20),
        },
        tsv=tsv,
    )


def run_positions_display(tsv: bool = False):
    """Display current positions and their details."""
    broker = ZerodhaBroker()
    positions = broker.get_current_positions()

    display_portfolio_table(
        positions,
        label_map={
            "symbol": ("Symbol", 12),
            "action": ("Action", 10),
            "buy_price": ("Average Price", 20),
            "quantity": ("Quantity", 10),
        },
        tsv=tsv,
    )


def run_rank(
    date: str, weights: str, top_n: int, save_results: bool, force_refresh: bool
):
    """Get stock rankings for a specific date."""
    try:
        # Parse and validate date
        as_of_date = pd.to_datetime(date)
        print(f"🎯 Calculating rankings for: {as_of_date.strftime('%Y-%m-%d')}")

        # Parse and validate weights
        try:
            weight_list = [float(w.strip()) for w in weights.split(",")]
            if len(weight_list) != 3:
                raise ValueError("Weights must have exactly 3 values")
            if abs(sum(weight_list) - 1.0) > 0.001:
                raise ValueError("Weights must sum to 1.0")
            ranking_weights = tuple(weight_list)
            print(
                f"📊 Using weights: Return={ranking_weights[0]:.1f}, RSI={ranking_weights[1]:.1f}, Proximity={ranking_weights[2]:.1f}"
            )
        except ValueError as e:
            print(f"❌ Invalid weights: {e}")
            print("💡 Example format: '0.8,0.1,0.1' (must sum to 1.0)")
            raise typer.Exit(1)

        # Get universe symbols
        print("🌍 Fetching universe symbols...")
        universe_symbols = get_universe_symbols("nifty500")
        print(f"📈 Raw universe size: {len(universe_symbols)} stocks")

        # Add benchmark
        symbols_to_fetch = ["^CRSLDX"] + [f"{symbol}.NS" for symbol in universe_symbols]

        # Calculate required start date (400 days buffer)
        start_date = (as_of_date - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = as_of_date.strftime("%Y-%m-%d")

        # Check cache status and refresh if needed
        print(f"🗂️ Checking cache for data from {start_date} to {end_date}...")

        if force_refresh or is_cache_stale_or_missing(
            symbols_to_fetch, start=start_date
        ):
            print("🔄 Cache is stale or missing data. Refreshing...")
            price_data = download_and_cache_prices(
                symbols_to_fetch, start=start_date, end=end_date
            )
        else:
            print("✅ Cache is fresh. Loading data from cache...")
            price_data = download_and_cache_prices(
                symbols_to_fetch, start=start_date, end=end_date
            )

        if not price_data:
            print("❌ Failed to load price data")
            raise typer.Exit(1)

        print(f"📊 Loaded price data for {len(price_data)} symbols")

        # Check market regime
        market_strong = is_market_strong(
            price_data, benchmark_symbol="^CRSLDX", as_of_date=as_of_date
        )

        print(
            f"📈 Market regime on {date}: {'🟢 STRONG' if market_strong else '🔴 WEAK'}"
        )

        if not market_strong:
            print("⚠️ Market is weak. Strategy would not take positions on this date.")
            return

        # Calculate rankings
        print("🏆 Calculating momentum rankings...")
        from logic.ranking import rank

        ranked_df = rank(price_data, as_of_date, weights=ranking_weights)

        if ranked_df.empty:
            print("❌ No stocks passed the ranking criteria")
            raise typer.Exit(1)

        # Add final rank column
        ranked_df["rank"] = ranked_df["total_rank"].rank(method="first").astype(int)
        ranked_df = ranked_df.sort_values("rank")

        # Clean symbol names for display
        ranked_df["clean_symbol"] = ranked_df["symbol"].str.replace(
            ".NS", "", regex=False
        )

        # Display top results
        display_df = ranked_df.head(top_n)[
            [
                "rank",
                "clean_symbol",
                "return_score",
                "rsi_score",
                "proximity_score",
                "total_rank",
            ]
        ]
        display_df.columns = [
            "Rank",
            "Symbol",
            "Return Score",
            "RSI Score",
            "Proximity Score",
            "Total Rank",
        ]

        print(f"\n🏆 TOP {top_n} RANKED STOCKS FOR {date}")
        print("=" * 90)
        print(display_df.to_string(index=False, float_format="{:.2f}".format))
        print("=" * 90)
        print(f"📊 Total stocks ranked: {len(ranked_df)}")

        # Save results if requested
        if save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ranked-stocks-{date}_{timestamp}.csv"

            # Use our caching system to save the output

            filepath = os.path.join("output", filename)
            # Convert to records for storage
            records = ranked_df.to_dict("records")
            if save_to_file(records, filepath):
                print(f"📁 Results saved to: {filepath}")
            else:
                print("⚠️ Caching is disabled - rankings were not saved to disk")

    except Exception as e:
        print(f"❌ Ranking failed: {e}")
        raise typer.Exit(1)
