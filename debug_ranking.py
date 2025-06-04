import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import argparse

from data.universe_fetcher import get_universe_symbols
from data.price_fetcher import download_and_cache_prices
from logic.ranking import rank
from utils.market import is_market_strong

def generate_ranking_csv(as_of_date: str, output_dir: str = "output", use_cached_data: bool = True) -> pd.DataFrame:
    """
    Generate a ranking CSV file for the given date.
    
    Args:
        as_of_date: Date for which to generate rankings (YYYY-MM-DD)
        output_dir: Directory to save the output file
        use_cached_data: If True, uses already cached data without re-downloading
        
    Returns:
        DataFrame containing the rankings
    """
    # Convert string date to timestamp
    as_of_date_ts = pd.to_datetime(as_of_date)
    print(f"🗓️ Generating rankings for {as_of_date_ts.strftime('%Y-%m-%d')}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get universe symbols
    universe = get_universe_symbols("nifty500")
    print(f"📈 Fetched universe with {len(universe)} symbols")
    
    # Add suffix for Yahoo Finance
    symbols_yf = [f"{s}.NS" for s in universe] + ["^NSEI"]
    
    if use_cached_data:
        # Use cached data without downloading again
        print(f"🔄 Using cached price data for {as_of_date}...")
        
        # Load each symbol's data from cache
        price_data = {}
        cache_dir = "cache/prices"
        
        for symbol in symbols_yf:
            try:
                path = os.path.join(cache_dir, f"{symbol}.csv")
                if os.path.exists(path):
                    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
                    # Filter data up to the as_of_date
                    df = df[df.index <= as_of_date_ts]
                    if not df.empty:
                        price_data[symbol] = df
            except Exception as e:
                print(f"⚠️ Error loading cached data for {symbol}: {e}")
        
        print(f"✅ Loaded cached data for {len(price_data)} symbols")
    else:
        # Download price data (include a year of historical data for indicators)
        start_date = (as_of_date_ts - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = as_of_date_ts.strftime("%Y-%m-%d")
        print(f"📊 Downloading price data from {start_date} to {end_date}...")
        
        price_data = download_and_cache_prices(symbols_yf, start=start_date, end=end_date)
        print(f"✅ Downloaded data for {len(price_data)} symbols")
    
    # Check if we have benchmark data
    if "^NSEI" not in price_data:
        print("❌ Error: Missing benchmark data (^NSEI)")
        return pd.DataFrame()
    
    # Check market regime
    benchmark_df = price_data.get("^NSEI")
    benchmark_df = benchmark_df[benchmark_df.index <= as_of_date_ts]
    
    market_strong = is_market_strong(benchmark_df) 
    print(f"🔍 Market regime: {'Strong 💪' if market_strong else 'Weak 📉'}")
    
    if not market_strong:
        print("⚠️ Warning: Market is not in a strong regime. Rankings may not be used for investment.")
    
    # Apply ranking logic
    ranked_df = rank(price_data, as_of_date_ts)
    
    if ranked_df.empty:
        print("❌ Error: No stocks passed the ranking filters")
        return ranked_df
    
    # Format and save to CSV
    ranked_df["rank"] = ranked_df["total_rank"].rank(method="first").astype(int)
    ranked_df = ranked_df.sort_values("rank")
    
    # Add symbol without .NS suffix for readability
    ranked_df["ticker"] = ranked_df["symbol"].str.replace(".NS", "", regex=False)
    
    # Save to CSV
    output_file = os.path.join(output_dir, f"ranking-{as_of_date}.csv")
    ranked_df.to_csv(output_file, index=False)
    print(f"✅ Saved rankings to {output_file}")
    print(f"📊 {len(ranked_df)} stocks passed all filters")
    
    return ranked_df

def debug_ranking(as_of_date: Optional[str] = None):
    """
    Debug the ranking system for a specific date.
    
    Args:
        as_of_date: Date for which to generate rankings (YYYY-MM-DD)
                   If None, use yesterday's date or last trading day
    """
    if as_of_date is None:
        # Use yesterday's date by default
        as_of_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    generate_ranking_csv(as_of_date)

def download_price_data_range(start_date: str, end_date: str = None):
    """
    Pre-download all price data for a given date range.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (defaults to today)
    """
    # Convert dates to timestamps
    start_date_ts = pd.to_datetime(start_date)
    if end_date:
        end_date_ts = pd.to_datetime(end_date)
    else:
        end_date_ts = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
        
    # Calculate data download start date (400 days before the analysis start date)
    download_start_ts = start_date_ts - timedelta(days=400)
    download_start = download_start_ts.strftime("%Y-%m-%d")
    download_end = end_date_ts.strftime("%Y-%m-%d")
    
    print(f"🗓️ Pre-downloading price data")
    print(f"📅 Analysis period: {start_date} to {download_end}")
    print(f"📊 Download period: {download_start} to {download_end} (including 400-day lookback)")
    
    # Get universe symbols
    universe = get_universe_symbols("nifty500")
    print(f"📈 Fetched universe with {len(universe)} symbols")
    
    # Add suffix for Yahoo Finance
    symbols_yf = [f"{s}.NS" for s in universe] + ["^NSEI"]
    
    # Download price data
    print(f"⏳ Downloading historical data for {len(symbols_yf)} symbols...")
    price_data = download_and_cache_prices(symbols_yf, start=download_start, end=download_end)
    
    print(f"✅ Downloaded data for {len(price_data)} symbols")
    print(f"💾 Data saved to cache/prices/ folder")
    
    return price_data

def analyze_rankings_over_time(start_date: str, end_date: str = None, interval: str = "W-FRI", output_dir: str = "output/analysis"):
    """
    Generate and analyze rankings over a series of dates.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (defaults to today)
        interval: Date frequency - 'W-FRI' for weekly Fridays, 'M' for month-end
        output_dir: Directory to save analysis results
    
    Returns:
        DataFrame containing metrics about ranking stability and volatility
    """
    # Convert dates to timestamps
    start_date_ts = pd.to_datetime(start_date)
    if end_date:
        end_date_ts = pd.to_datetime(end_date)
    else:
        end_date_ts = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
    
    # Generate date range according to interval
    if interval == "W-FRI":
        dates = pd.date_range(start=start_date_ts, end=end_date_ts, freq=interval)
    elif interval == "M":
        dates = pd.date_range(start=start_date_ts, end=end_date_ts, freq=interval)
    else:
        # Default to weekly rebalance on Fridays
        dates = pd.date_range(start=start_date_ts, end=end_date_ts, freq="W-FRI")
    
    print(f"📅 Analyzing rankings from {start_date} to {end_date_ts.strftime('%Y-%m-%d')}")
    print(f"📊 Total dates to analyze: {len(dates)}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize tracking variables
    all_rankings = {}
    stability_metrics = []
    
    # Analyze each date
    for i, date in enumerate(dates):
        date_str = date.strftime("%Y-%m-%d")
        print(f"\n[{i+1}/{len(dates)}] Analyzing {date_str}")
        
        # Generate rankings for this date
        rankings = generate_ranking_csv(date_str, output_dir)
        
        if rankings.empty:
            print(f"⚠️ No rankings for {date_str}, skipping")
            continue
        
        # Store rankings
        all_rankings[date_str] = rankings
        
        # Calculate stability metrics if we have previous rankings
        if i > 0:
            prev_date_str = dates[i-1].strftime("%Y-%m-%d")
            prev_rankings = all_rankings.get(prev_date_str)
            
            if prev_rankings is not None and not prev_rankings.empty:
                stability_data = calculate_ranking_stability(rankings, prev_rankings)
                stability_metrics.append({
                    'date': date_str,
                    'prev_date': prev_date_str,
                    **stability_data
                })
    
    # Save stability metrics
    if stability_metrics:
        stability_df = pd.DataFrame(stability_metrics)
        stability_file = os.path.join(output_dir, "ranking_stability.csv")
        stability_df.to_csv(stability_file, index=False)
        print(f"\n✅ Saved stability metrics to {stability_file}")
        
        # Print summary
        print("\n📊 Ranking Stability Summary:")
        print(f"Average rank change: {stability_df['avg_rank_change'].mean():.2f}")
        print(f"Max rank change: {stability_df['max_rank_change'].mean():.2f}")
        print(f"Average churn %: {stability_df['churn_pct'].mean():.2f}%")
        print(f"Correlation between ranks: {stability_df['rank_correlation'].mean():.2f}")
        
        return stability_df
    else:
        print("⚠️ No stability metrics calculated")
        return pd.DataFrame()

def calculate_ranking_stability(current_rankings: pd.DataFrame, previous_rankings: pd.DataFrame):
    """
    Calculate ranking stability metrics between two ranking periods.
    
    Args:
        current_rankings: Current period rankings DataFrame
        previous_rankings: Previous period rankings DataFrame
        
    Returns:
        Dictionary of stability metrics
    """
    # Clean symbols for comparison
    current_rankings_clean = current_rankings.copy()
    current_rankings_clean['symbol_clean'] = current_rankings_clean['symbol'].str.replace('.NS', '')
    
    previous_rankings_clean = previous_rankings.copy()
    previous_rankings_clean['symbol_clean'] = previous_rankings_clean['symbol'].str.replace('.NS', '')
    
    # Merge the rankings
    merged = current_rankings_clean.merge(
        previous_rankings_clean[['symbol_clean', 'rank']],
        on='symbol_clean',
        how='outer',
        suffixes=('', '_prev')
    )
    
    # Calculate metrics for stocks present in both periods
    both_periods = merged.dropna(subset=['rank', 'rank_prev'])
    
    # Calculate rank changes
    both_periods['rank_change'] = abs(both_periods['rank'] - both_periods['rank_prev'])
    
    # Calculate top N overlap (for N=15, typical portfolio size)
    top_n = 15
    current_top_n = set(current_rankings_clean.nsmallest(top_n, 'rank')['symbol_clean'])
    previous_top_n = set(previous_rankings_clean.nsmallest(top_n, 'rank')['symbol_clean'])
    
    overlap = len(current_top_n.intersection(previous_top_n))
    churn_pct = 100 * (1 - overlap / top_n)
    
    # Calculate rank correlation
    if len(both_periods) > 1:
        rank_correlation = both_periods['rank'].corr(both_periods['rank_prev'])
    else:
        rank_correlation = 0
    
    return {
        'total_stocks': len(current_rankings),
        'common_stocks': len(both_periods),
        'avg_rank_change': both_periods['rank_change'].mean(),
        'median_rank_change': both_periods['rank_change'].median(),
        'max_rank_change': both_periods['rank_change'].max(),
        'top_15_overlap': overlap,
        'churn_pct': churn_pct,
        'rank_correlation': rank_correlation
    }

def main():
    """
    Main entry point with command-line interface
    """
    parser = argparse.ArgumentParser(description="Stock ranking analysis tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Ranking command
    rank_parser = subparsers.add_parser("rank", help="Generate stock rankings for a specific date")
    rank_parser.add_argument(
        "--date", 
        "-d", 
        type=str,
        help="Date for ranking in YYYY-MM-DD format (default: yesterday)",
        required=False
    )
    rank_parser.add_argument(
        "--output", 
        "-o", 
        type=str,
        default="output",
        help="Output directory (default: 'output')",
        required=False
    )
    rank_parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force download price data instead of using cache",
        required=False
    )
    
    # Download data command
    download_parser = subparsers.add_parser("download", help="Pre-download price data for a date range")
    download_parser.add_argument(
        "--start", 
        "-s", 
        type=str,
        required=True,
        help="Start date in YYYY-MM-DD format"
    )
    download_parser.add_argument(
        "--end", 
        "-e", 
        type=str,
        required=False,
        help="End date in YYYY-MM-DD format (default: today)"
    )
    
    # Analyze rankings command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze rankings over a period")
    analyze_parser.add_argument(
        "--start", 
        "-s", 
        type=str,
        required=True,
        help="Start date in YYYY-MM-DD format"
    )
    analyze_parser.add_argument(
        "--end", 
        "-e", 
        type=str,
        required=False,
        help="End date in YYYY-MM-DD format (default: today)"
    )
    analyze_parser.add_argument(
        "--interval", 
        "-i", 
        type=str,
        default="W-FRI",
        choices=["W-FRI", "W-WED", "W-MON", "M"],
        help="Rebalance frequency: W-FRI (Fridays), W-WED (Wednesdays), M (month-end)"
    )
    analyze_parser.add_argument(
        "--output", 
        "-o", 
        type=str,
        default="output/analysis",
        help="Output directory for analysis results"
    )
    
    args = parser.parse_args()
    
    # Process commands
    if args.command == "rank" or not args.command:
        # Default to rank command if none specified
        date_param = args.date if hasattr(args, 'date') and args.date else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        use_cached = not hasattr(args, 'force_download') or not args.force_download
        output_dir = args.output if hasattr(args, 'output') and args.output else "output"
        generate_ranking_csv(date_param, output_dir, use_cached_data=use_cached)
    elif args.command == "download":
        download_price_data_range(args.start, args.end)
    elif args.command == "analyze":
        analyze_rankings_over_time(args.start, args.end, args.interval, args.output)
    
if __name__ == "__main__":
    main()

