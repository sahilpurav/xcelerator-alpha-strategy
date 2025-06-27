import os
import pandas as pd
import yfinance as yf
from typing import Optional
from datetime import datetime
from utils.market import is_market_open_now
from utils.market import get_last_trading_date
from utils.cache import is_caching_enabled, load_from_file, save_to_file

def is_cache_stale_or_missing(symbols: list[str], start: str | None = None, cache_dir: str = "cache/prices") -> bool:
    """
    Checks if the cache for the given symbols is stale or missing.
    Also verifies that the cache contains the required historical range if start date is provided.
    Returns True if cache is stale or missing, False otherwise.
    """
    # If caching is disabled, always return True to force fresh data
    if not is_caching_enabled():
        # Print a debug message to make it clear we're skipping cache
        print("⚠️ Caching is disabled, using fresh data...")
        return True
        
    if not symbols:
        return True

    # Always check ^CRSLDX first if it's in the list
    check_symbol = "^CRSLDX" if "^CRSLDX" in symbols else symbols[0]
    check_path = os.path.join(cache_dir, f"{check_symbol}.csv")

    # Check if cache exists
    if not os.path.exists(check_path):
        print(f"🛑 Cache missing for {check_symbol}")
        return True

    try:
        # Get data using the utility function
        cached_data = load_from_file(check_path)
        if not cached_data or not isinstance(cached_data, list) or not cached_data:
            print(f"🛑 Invalid or empty cache for {check_symbol}")
            return True
            
        # Convert to DataFrame
        df = pd.DataFrame(cached_data)
        
        # Check if "Date" column exists
        if "Date" not in df.columns:
            print(f"🛑 Invalid cache format for {check_symbol}: missing 'Date' column")
            return True
            
        # Set Date as index after verifying it exists
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        
        # Check if we have enough historical data
        if start:
            required_start = pd.to_datetime(start)  # Use start date as is
            earliest_cached = pd.to_datetime(df.index.min()).normalize()
            
            if earliest_cached > required_start:
                print(f"📉 Cache doesn't have enough history:")
                print(f"   ├── Earliest cached: {earliest_cached.date()}")
                print(f"   ├── Required start : {required_start.date()}")
                print(f"   └── Missing {(earliest_cached - required_start).days} days of history")
                return True

        # Check if we have latest data
        last_cached_date = pd.to_datetime(df.index.max()).normalize()
        last_trading_day = pd.to_datetime(get_last_trading_date()).normalize()

        if last_cached_date < last_trading_day:
            print(f"📉 Cache is stale: last cached = {last_cached_date.date()}, expected = {last_trading_day.date()}")
            return True

        # Check if other symbols exist
        for symbol in symbols:
            if not os.path.exists(os.path.join(cache_dir, f"{symbol}.csv")):
                print(f"🛑 Cache missing for {symbol}")
                return True

    except Exception as e:
        print(f"⚠️ Error reading cache for {check_symbol}: {e}")
        return True

    return False


def download_and_cache_prices(
    symbols: list[str],
    start: str,
    end: Optional[str] = None,
    cache_dir: str = "cache/prices"
) -> dict[str, pd.DataFrame]:
    """
    Downloads historical price data for given symbols and caches it locally.
    If the cache is fresh, it loads data from cache instead of downloading.
    Returns a dictionary of DataFrames indexed by symbol.
    """
    # If no end date is provided, use today's date
    end = end or datetime.today().strftime('%Y-%m-%d')

    # ⚠️ Yahoo's `end` parameter is exclusive — to include the last trading day,
    # we need to shift it by +1 day
    end_dt = pd.to_datetime(end) + pd.Timedelta(days=1)
    end = end_dt.strftime('%Y-%m-%d')

    live_market = is_market_open_now()
    
    # Only create cache directories and check cache if caching is enabled
    if is_caching_enabled():
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load from cache if everything is valid and fresh
        if not is_cache_stale_or_missing(symbols, start=start, cache_dir=cache_dir) and not live_market:
            print("✅ Cache is fresh and contains required history. Loading all symbols locally...")
            result = {}
            for symbol in symbols:
                try:
                    path = os.path.join(cache_dir, f"{symbol}.csv")
                    # Load the raw data with the utility function
                    cached_data = load_from_file(path)
                    if cached_data:
                        # Convert to pandas DataFrame and handle Date formatting
                        df = pd.DataFrame(cached_data)
                        # Make an explicit copy before modifying
                        df = df.copy()
                        df["Date"] = pd.to_datetime(df["Date"])
                        
                        # Ensure numeric columns are converted to float
                        numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
                        for col in numeric_columns:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors='coerce')
                                
                        df = df.set_index("Date").sort_index()
                        result[symbol] = df
                    else:
                        print(f"⚠️ Cache missing for {symbol}")
                except Exception as e:
                    print(f"⚠️ Failed to load cache for {symbol}: {e}")
            return result
    
    if live_market:
        print("⚠️ Live market detected. Ignoring the cache and using fresh prices.")

    # Download fresh data
    print(f"📥 Downloading {len(symbols)} symbols from {start} to {end}...")
    try:
        data = yf.download(
            tickers=symbols,
            start=start,  # Use start date as provided (buffer already added in backtest.py)
            end=end,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False
        )
    except Exception as e:
        print(f"❌ Batch download failed: {e}")
        return {}

    result = {}

    for symbol in symbols:
        try:
            df = data[symbol] if isinstance(data.columns, pd.MultiIndex) else data
            df = df.dropna()
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            # Make an explicit copy to avoid SettingWithCopyWarning
            df = df.rename_axis("Date").reset_index().set_index("Date").sort_index().copy()
            
            # Ensure numeric columns are in the correct format
            numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            result[symbol] = df

            # Only attempt to save to cache if caching is enabled
            if is_caching_enabled() and not live_market:
                try:
                    cached_path = os.path.join(cache_dir, f"{symbol}.csv")
                    # Convert DataFrame to records for storage (list of dictionaries)
                    df_to_save = df.reset_index()  # Make sure Date is a column, not index
                    records = df_to_save.to_dict('records')
                    # Use the utility function to save
                    save_to_file(records, cached_path)
                except Exception as e:
                    print(f"⚠️ Failed to cache {symbol}: {e}")
        except Exception as e:
            print(f"⚠️ Failed processing {symbol}: {e}")

    return result
