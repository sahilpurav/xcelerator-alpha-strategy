import os
from datetime import datetime

import pandas as pd
import yfinance as yf

from utils.cache import is_caching_enabled, load_from_file, save_to_file


def is_cache_stale_or_missing(
    symbols: list[str], start: str | None = None, cache_dir: str = "cache/prices"
) -> bool:
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

    # Check which benchmark symbol to use for cache validation
    # Priority: ^CRSLDX (nifty500), then ^CNX100 (nifty100), then first symbol
    check_symbol = None
    if "^CRSLDX" in symbols:
        check_symbol = "^CRSLDX"
    elif "^CNX100" in symbols:
        check_symbol = "^CNX100"
    else:
        check_symbol = symbols[0]
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
                print(
                    f"   └── Missing {(earliest_cached - required_start).days} days of history"
                )
                return True

    except Exception as e:
        print(f"⚠️ Error reading cache for {check_symbol}: {e}")
        return True

    return False

def download_fresh_prices(symbols: list[str], start: str, end: str, cache_dir: str = "cache/prices") -> dict[str, pd.DataFrame]:
    """
    Downloads price data for the given symbols and caches them if caching is enabled.
    
    Args:
        symbols: List of ticker symbols to download
        start: Start date for historical data
        end: End date for historical data
        cache_dir: Directory to store cached data
        
    Returns:
        Dictionary of DataFrames indexed by symbol
    """
    print(f"📥 Downloading {len(symbols)} symbols from {start} to {end}...")
    try:
        data = yf.download(
            tickers=symbols,
            start=start,
            end=end,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"❌ Batch download failed: {e}")
        return {}

    result = {}

    for symbol in symbols:
        try:
            df = data[symbol] if isinstance(data.columns, pd.MultiIndex) else data
            df = df.dropna()
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            # Make an explicit copy to avoid SettingWithCopyWarning
            df = (
                df.rename_axis("Date")
                .reset_index()
                .set_index("Date")
                .sort_index()
                .copy()
            )

            # Ensure numeric columns are in the correct format
            numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            result[symbol] = df

            # Only attempt to save to cache if caching is enabled
            if is_caching_enabled():
                try:
                    cached_path = os.path.join(cache_dir, f"{symbol}.csv")
                    # Convert DataFrame to records for storage (list of dictionaries)
                    df_to_save = df.reset_index()  # Make sure Date is a column, not index
                    records = df_to_save.to_dict("records")
                    # Use the utility function to save
                    save_to_file(records, cached_path)
                except Exception as e:
                    print(f"⚠️ Failed to cache {symbol}: {e}")
        except Exception as e:
            print(f"⚠️ Failed processing {symbol}: {e}")

    return result


def download_and_cache_prices(
    symbols: list[str],
    start: str,
    end: str | None = None,
    cache_dir: str = "cache/prices",
) -> dict[str, pd.DataFrame]:
    """
    Downloads historical price data for given symbols and caches it locally.
    If the cache is fresh, it loads data from cache instead of downloading.
    Returns a dictionary of DataFrames indexed by symbol.
    """
    # If no end date is provided, use today's date
    end = end or datetime.today().strftime("%Y-%m-%d")

    # ⚠️ Yahoo's `end` parameter is exclusive — to include the last trading day,
    # we need to shift it by +1 day
    end_dt = pd.to_datetime(end) + pd.Timedelta(days=1)
    end = end_dt.strftime("%Y-%m-%d")

    # If caching is disabled, download fresh data for all symbols
    if not is_caching_enabled():
        print("⚠️ Caching is disabled, downloading fresh data...")
        return download_fresh_prices(symbols, start, end, cache_dir)

    # Create cache directory
    os.makedirs(cache_dir, exist_ok=True)

    # Check if cache is stale
    if is_cache_stale_or_missing(symbols, start=start, cache_dir=cache_dir):
        print("⚠️ Cache is stale or missing, downloading fresh data...")
        return download_fresh_prices(symbols, start, end, cache_dir)

    # Cache is fresh, try to load symbols from cache
    print("✅ Cache is fresh and contains required history. Loading all symbols locally...")
    result = {}
    symbols_with_missing_price = []

    # Loop through all symbols and try to load from cache
    for symbol in symbols:
        try:
            path = os.path.join(cache_dir, f"{symbol}.csv")
            cached_data = load_from_file(path)
            
            if not cached_data:
                symbols_with_missing_price.append(symbol)
                continue

            # Convert to pandas DataFrame and handle Date formatting
            df = pd.DataFrame(cached_data)
            df = df.copy()
            df["Date"] = pd.to_datetime(df["Date"])

            # Ensure numeric columns are converted to float
            numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df = df.set_index("Date").sort_index()
            result[symbol] = df

        except Exception as e:
            print(f"⚠️ Failed to load cache for {symbol}: {e}")
            symbols_with_missing_price.append(symbol)

    # If there are symbols with missing prices, download them
    if symbols_with_missing_price:
        print(
            f"⚠️ Some symbols ({', '.join(symbols_with_missing_price)}) "
            "are missing from cache or have invalid data."
        )
        missing_data = download_fresh_prices(symbols_with_missing_price, start, end, cache_dir)
        result.update(missing_data)
    else:
        print("✅ All symbols loaded successfully from cache.")
    
    return result
