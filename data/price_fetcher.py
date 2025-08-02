import os
from datetime import datetime, timedelta
from time import sleep
from typing import Optional

import pandas as pd

from broker.zerodha import ZerodhaBroker
from utils.cache import is_caching_enabled, load_from_file, save_to_file
from utils.market import get_market_status


def fetch_price_from_kite(kite, instrument_token: int, from_date: str, to_date: str) -> pd.DataFrame:
    """
    Fetches historical price data from Kite API for a given instrument token.
    Returns a DataFrame with OHLCV data.
    """
    try:
        # Convert dates to datetime objects for Kite API
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        
        # Fetch historical data from Kite
        historical_data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_dt,
            to_date=to_dt,
            interval="day"
        )
        
        if not historical_data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(historical_data)
        
        # Rename columns to match expected format
        column_mapping = {
            "date": "Date",
            "open": "Open",
            "high": "High", 
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
        
        df = df.rename(columns=column_mapping)
        
        # Ensure Date is datetime and set as index
        df["Date"] = pd.to_datetime(df["Date"])
        # Convert timezone-aware dates to timezone-naive by localizing to UTC then converting to naive
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.set_index("Date")
        
        # Ensure numeric columns
        numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df.sort_index()
        
    except Exception as e:
        print(f"❌ Failed to fetch data from Kite for token {instrument_token}: {e}")
        return pd.DataFrame()


def load_cached_prices(symbol: str, cache_dir: str = "cache/prices") -> Optional[pd.DataFrame]:
    """
    Loads cached price data for a symbol.
    Returns None if cache doesn't exist or is invalid.
    """
    cache_path = os.path.join(cache_dir, f"{symbol}.csv")
    
    if not os.path.exists(cache_path):
        return None
    
    try:
        cached_data = load_from_file(cache_path)
        if not cached_data:
            return None
        
        df = pd.DataFrame(cached_data)
        if "Date" not in df.columns or df.empty:
            return None
        
        # Convert Date to datetime and set as index
        df["Date"] = pd.to_datetime(df["Date"])
        # Convert timezone-aware dates to timezone-naive by localizing to UTC then converting to naive
        if df["Date"].dt.tz is not None:
            df["Date"] = df["Date"].dt.tz_localize(None)
        df = df.set_index("Date")
        
        # Ensure numeric columns
        numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df.sort_index()
        
    except Exception as e:
        print(f"⚠️ Error loading cache for {symbol}: {e}")
        return None


def save_prices_to_cache(df: pd.DataFrame, symbol: str, cache_dir: str = "cache/prices"):
    """
    Saves price data to cache for a symbol.
    """
    if not is_caching_enabled():
        return
    
    try:
        cache_path = os.path.join(cache_dir, f"{symbol}.csv")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Convert DataFrame to records for storage
        df_to_save = df.reset_index()  # Make Date a column
        records = df_to_save.to_dict("records")
        
        save_to_file(records, cache_path)
        print(f"✅ Cached {len(df)} records for {symbol}")
        
    except Exception as e:
        print(f"⚠️ Failed to cache {symbol}: {e}")


def get_prices(symbols: list[str], start: str, end: Optional[str] = None) -> dict[str, pd.DataFrame]:
    """
    Main function to get historical price data for symbols.
    
    Args:
        symbols: List of trading symbols
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format (optional, defaults to last trading day)
    
    Returns:
        Dictionary mapping symbols to DataFrames with OHLCV data
    """
    if not symbols:
        return {}
    
    # Initialize Zerodha broker
    try:
        broker = ZerodhaBroker()
        kite = broker.kite
        instrument_token_map = broker.get_instrument_token_map()
    except Exception as e:
        print(f"❌ Failed to initialize Zerodha broker: {e}")
        return {}
    
    # Get market status to determine end date
    market_status = get_market_status()
    is_market_open = market_status["marketStatus"] in ["Open"]
    
    # Determine end date
    if end is None:
        if is_market_open:
            # If market is open, use yesterday as end date
            end_date = datetime.now() - timedelta(days=1)
            end = end_date.strftime("%Y-%m-%d")
            print(f"📅 Market is open, using yesterday ({end}) as end date")
        else:
            # If market is closed, use today as end date
            end = datetime.now().strftime("%Y-%m-%d")
            print(f"📅 Market is closed, using today ({end}) as end date")
    
    print(f"📊 Fetching prices for {len(symbols)} symbols from {start} to {end}")
    
    result = {}
    
    for symbol in symbols:
        print(f"🔍 Processing {symbol}...")
        
        # Check if symbol exists in instrument token map
        if symbol not in instrument_token_map:
            print(f"⚠️ Symbol {symbol} not found in instrument token map, skipping")
            continue
        
        instrument_token = instrument_token_map[symbol]
        
        # Try to load from cache first
        cached_df = load_cached_prices(symbol)
        
        if cached_df is not None and not cached_df.empty:
            # Check if we have enough data
            cached_start = cached_df.index.min()
            cached_end = cached_df.index.max()
            required_start = pd.to_datetime(start)
            required_end = pd.to_datetime(end)
            
            # If cache covers the required range, use it
            if cached_start <= required_start and cached_end >= required_end:
                print(f"✅ Using cached data for {symbol}")
                result[symbol] = cached_df[required_start:required_end]
                continue
            
            # If cache is missing some data, fetch only the missing part
            fetch_start = start
            fetch_end = end
            
            # Handle new listings: if symbol was listed after strategy start date
            if cached_start > required_start:
                print(f"📅 {symbol} was listed on {cached_start.strftime('%Y-%m-%d')} (after strategy start {required_start.strftime('%Y-%m-%d')})")
                # For new listings, we can only provide data from listing date onwards
                if cached_end >= required_end:
                    # We have enough data from listing date to end date
                    print(f"✅ Using cached data for {symbol} from listing date")
                    result[symbol] = cached_df[required_start:required_end]
                    continue
                else:
                    # Need to fetch incremental data from listing date onwards
                    fetch_start = (cached_end + timedelta(days=1)).strftime("%Y-%m-%d")
                    print(f"📈 Fetching incremental data for {symbol} from {fetch_start}")
            elif cached_end >= required_start:
                # We have some overlapping data, fetch from last cached date + 1
                fetch_start = (cached_end + timedelta(days=1)).strftime("%Y-%m-%d")
                print(f"📈 Fetching incremental data for {symbol} from {fetch_start}")
            else:
                # Cache is too old, fetch from required start
                print(f"📉 Cache too old for {symbol}, fetching from {fetch_start}")
            
            # Validate that fetch_start is not after fetch_end
            if pd.to_datetime(fetch_start) > pd.to_datetime(fetch_end):
                print(f"⚠️ Skip fetching incremental data for {symbol}: fetch_start ({fetch_start}) is after fetch_end ({fetch_end})")
                # Use cached data if it covers required range
                if cached_start <= required_start and cached_end >= required_end:
                    result[symbol] = cached_df[required_start:required_end]
                else:
                    print(f"⚠️ Failed to fetch data for {symbol}")
                continue
            
            # Fetch missing data
            sleep(0.5)
            new_df = fetch_price_from_kite(kite, instrument_token, fetch_start, fetch_end)
            
            if not new_df.empty:
                # Combine cached and new data
                combined_df = pd.concat([cached_df, new_df])
                combined_df = combined_df[~combined_df.index.duplicated(keep='last')]  # Remove duplicates
                combined_df = combined_df.sort_index()
                
                # Save updated cache
                save_prices_to_cache(combined_df, symbol)
                
                # Return data for requested range
                result[symbol] = combined_df[required_start:required_end]
            else:
                # If new fetch failed, use cached data if it covers required range
                if cached_start <= required_start and cached_end >= required_end:
                    result[symbol] = cached_df[required_start:required_end]
                else:
                    print(f"⚠️ Failed to fetch data for {symbol}")
        else:
            sleep(0.5)
            # No cache exists, fetch all data
            print(f"📥 Fetching fresh data for {symbol}")
            df = fetch_price_from_kite(kite, instrument_token, start, end)
            
            if not df.empty:
                # Save to cache
                save_prices_to_cache(df, symbol)
                
                # Return data for requested range
                result[symbol] = df
            else:
                print(f"⚠️ Failed to fetch data for {symbol}")
    
    print(f"✅ Successfully fetched data for {len(result)} symbols")
    return result
