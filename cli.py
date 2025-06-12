import typer
import shutil
import os
from typing import Optional, List
from execution.live import run_initial_investment, run_rebalance, run_topup_only
from execution.backtest import run_backtest
from broker.zerodha import ZerodhaBroker
from logic.display import display_portfolio_table
from optimization import WeightOptimizer
from optimization.utils import parse_weights_string, generate_test_combinations, save_optimization_results
from datetime import datetime
import pandas as pd
from data.universe_fetcher import get_universe_symbols
from logic.filters import apply_universe_filters
from data.price_fetcher import download_and_cache_prices, is_cache_stale_or_missing
from logic.strategy import get_ranked_stocks
from utils.market import is_market_strong

app = typer.Typer()

@app.command()
def clear_cache():
    """
    Delete all cached files and reset the strategy state.
    This will remove all cached price data and reset the strategy state.
    """
    if os.path.exists("cache"):
        shutil.rmtree("cache")
        print("🗑️ Removed 'cache' folder.")
    if os.path.exists("output"):
        shutil.rmtree("output")
        print("🗑️ Removed 'output' folder.")
    else:
        print("✅ Nothing to delete.")

@app.command()
def initial(
    top_n: int = typer.Option(15, prompt="📊 Enter number of stocks to invest in (top_n)"),
    amount: float = typer.Option(..., prompt="💰 Enter the total capital to invest (amount in ₹)")
):
    """
    Run initial investment interactively with prompts.
    """
    run_initial_investment(top_n=top_n, amount=amount)

@app.command()
def rebalance(preview: bool = False, band: int = 5):
    """Run weekly rebalance with optional fresh capital"""
    run_rebalance(preview=preview, band=band)

@app.command()
def topup(amount: float = typer.Option(..., prompt="💰 Enter the total capital to top-up (amount in ₹)"), preview: bool = False):
    """Top up capital in current holdings only"""
    run_topup_only(amount, preview=preview)

@app.command()
def holdings(tsv: bool = False):
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
        tsv=tsv
    )

    
@app.command()
def positions(tsv: bool = False):
    """Display current positions and their details."""
    broker = ZerodhaBroker()
    positions = broker.get_current_positions()

    display_portfolio_table(
        positions,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
        },
        tsv=tsv
    )


@app.command()
def backtest(
        start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
        end: Optional[str] = typer.Option(None, help="Optional end date (YYYY-MM-DD). Defaults to today."),
        rebalance_day: str = typer.Option("Wednesday", help="Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)"),
        band: int = typer.Option(5, help="Band size for portfolio stability (higher = less churn)")
):
    """
    Run the backtest for Xcelerator Alpha Strategy.

    Args:
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.
        rebalance_day (str): Day of week for rebalancing.
        band (int): Band size for portfolio stability (default 5).
    """
    run_backtest(start, end, rebalance_day, band)


@app.command()
def optimize_weights(
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    method: str = typer.Option("grid", help="Optimization method: 'grid' or 'scipy'"),
    step: float = typer.Option(0.1, help="Grid search step size (0.05 for fine, 0.1 for coarse, 0.2 for quick)"),
    max_dd: float = typer.Option(-20.0, help="Maximum allowed drawdown percentage (e.g., -20.0 for -20%)"),
    top_n: int = typer.Option(15, help="Number of stocks in portfolio"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    save_results: bool = typer.Option(True, help="Save results to CSV file")
):
    """
    Optimize ranking weights for the momentum strategy.
    
    This command finds the optimal weights for return_rank, rsi_rank, and proximity_rank
    that maximize CAGR while keeping drawdown below the specified threshold.
    
    Examples:
        python cli.py optimize-weights --start 2020-01-01 --method grid --step 0.1
        python cli.py optimize-weights --start 2020-01-01 --method scipy --max-dd -20
    """
    
    # Set end date to today if not provided
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    # Validate method
    if method not in ["grid", "scipy"]:
        print("❌ Error: method must be 'grid' or 'scipy'")
        raise typer.Exit(1)
    
    # Create optimizer
    optimizer = WeightOptimizer(
        start_date=start,
        end_date=end,
        max_drawdown_threshold=max_dd,
        top_n=top_n,
        band=band
    )
    
    try:
        print(f"🚀 Starting {method} optimization...")
        
        if method == "grid":
            results = optimizer.grid_search(weight_step=step, verbose=True)
        else:  # scipy
            results = optimizer.scipy_optimize(verbose=True)
        
        # Save results if requested
        if save_results and results.get('all_results') is not None:
            filename = f"weight_optimization_{method}_{start}_{end}.csv"
            save_optimization_results(results, filename)
        
    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        raise typer.Exit(1)


@app.command()
def compare_weights(
    weights: List[str] = typer.Argument(..., help="Weight combinations to compare (e.g., '0.8,0.1,0.1' '0.6,0.2,0.2')"),
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    max_dd: float = typer.Option(-20.0, help="Maximum allowed drawdown percentage"),
    top_n: int = typer.Option(15, help="Number of stocks in portfolio"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    include_common: bool = typer.Option(False, help="Include common test combinations"),
    save_results: bool = typer.Option(True, help="Save results to CSV file")
):
    """
    Compare specific weight combinations for the momentum strategy.
    
    Examples:
        python cli.py compare-weights "0.8,0.1,0.1" "0.6,0.2,0.2" --start 2020-01-01
        python cli.py compare-weights "0.5,0.3,0.2" --start 2020-01-01 --include-common
    """
    
    # Set end date to today if not provided
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    
    # Parse weight combinations
    weight_combinations = []
    
    try:
        for weight_str in weights:
            parsed_weights = parse_weights_string(weight_str)
            weight_combinations.append(parsed_weights)
    except ValueError as e:
        print(f"❌ Error parsing weights: {e}")
        print("💡 Example format: '0.8,0.1,0.1' (must sum to 1.0)")
        raise typer.Exit(1)
    
    # Add common test combinations if requested
    if include_common:
        common_combinations = generate_test_combinations()
        # Remove duplicates
        for combo in common_combinations:
            if combo not in weight_combinations:
                weight_combinations.append(combo)
    
    # Create optimizer
    optimizer = WeightOptimizer(
        start_date=start,
        end_date=end,
        max_drawdown_threshold=max_dd,
        top_n=top_n,
        band=band
    )
    
    try:
        results_df = optimizer.compare_combinations(weight_combinations)
        
        # Save results if requested
        if save_results and not results_df.empty:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"weight_comparison_{start}_{end}_{timestamp}.csv"
            
            # Ensure output directory exists
            if not os.path.exists("output"):
                os.makedirs("output")
            
            filepath = os.path.join("output", filename)
            results_df.to_csv(filepath, index=False)
            print(f"📁 Results saved to: {filepath}")
        
    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        raise typer.Exit(1)

@app.command()
def rank(
    date: str = typer.Option(..., help="Date for ranking (YYYY-MM-DD)"),
    weights: str = typer.Option("0.8,0.1,0.1", help="Ranking weights as 'return,rsi,proximity' (must sum to 1.0)"),
    top_n: int = typer.Option(50, help="Number of top stocks to display"),
    save_results: bool = typer.Option(True, help="Save results to CSV file"),
    force_refresh: bool = typer.Option(False, help="Force cache refresh even if data exists")
):
    """
    Get stock rankings for a specific date.
    
    This command calculates momentum rankings for all stocks in the universe 
    for the specified date. It intelligently manages cache, ensuring 400 days 
    of historical data is available before the ranking date.
    
    Examples:
        python cli.py rank --date 2024-01-15
        python cli.py rank --date 2024-01-15 --weights "0.7,0.2,0.1" --top-n 30
        python cli.py rank --date 2024-01-15 --force-refresh
    """
    
    try:
        # Parse and validate date
        as_of_date = pd.to_datetime(date)
        print(f"🎯 Calculating rankings for: {as_of_date.strftime('%Y-%m-%d')}")
        
        # Parse and validate weights
        try:
            weight_list = [float(w.strip()) for w in weights.split(',')]
            if len(weight_list) != 3:
                raise ValueError("Weights must have exactly 3 values")
            if abs(sum(weight_list) - 1.0) > 0.001:
                raise ValueError("Weights must sum to 1.0")
            ranking_weights = tuple(weight_list)
            print(f"📊 Using weights: Return={ranking_weights[0]:.1f}, RSI={ranking_weights[1]:.1f}, Proximity={ranking_weights[2]:.1f}")
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
        
        if force_refresh or is_cache_stale_or_missing(symbols_to_fetch, start=start_date):
            print("🔄 Cache is stale or missing data. Refreshing...")
            price_data = download_and_cache_prices(symbols_to_fetch, start=start_date, end=end_date)
        else:
            print("✅ Cache is fresh. Loading data from cache...")
            price_data = download_and_cache_prices(symbols_to_fetch, start=start_date, end=end_date)
        
        if not price_data:
            print("❌ Failed to load price data")
            raise typer.Exit(1)
        
        print(f"📊 Loaded price data for {len(price_data)} symbols")
        
        # Check market regime
        market_strong = is_market_strong(price_data, benchmark_symbol="^CRSLDX", as_of_date=as_of_date)
        
        print(f"📈 Market regime on {date}: {'🟢 STRONG' if market_strong else '🔴 WEAK'}")
        
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
        ranked_df["clean_symbol"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
        
        # Display top results
        display_df = ranked_df.head(top_n)[["rank", "clean_symbol", "return_score", "rsi_score", "proximity_score", "total_rank"]]
        display_df.columns = ["Rank", "Symbol", "Return Score", "RSI Score", "Proximity Score", "Total Rank"]
        
        print(f"\n🏆 TOP {top_n} RANKED STOCKS FOR {date}")
        print("=" * 90)
        print(display_df.to_string(index=False, float_format='{:.2f}'.format))
        print("=" * 90)
        print(f"📊 Total stocks ranked: {len(ranked_df)}")
        
        # Save results if requested
        if save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ranked-stocks-{date}_{timestamp}.csv"
            
            # Ensure output directory exists
            if not os.path.exists("output"):
                os.makedirs("output")
            
            filepath = os.path.join("output", filename)
            ranked_df.to_csv(filepath, index=False)
            print(f"📁 Results saved to: {filepath}")
        
    except Exception as e:
        print(f"❌ Ranking failed: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
