import os
import pandas as pd
import yfinance as yf
from typing import Optional
from datetime import datetime
from utils.date import is_market_open_now
from utils.date import get_last_trading_day

def is_cache_stale_or_missing(symbols: list[str], cache_dir: str = "cache/prices") -> bool:
    """
    Checks if the cache for the given symbols is stale or missing.
    Returns True if cache is stale or missing, False otherwise.
    """
    if not symbols:
        return True

    # Check if all cache files exist
    for symbol in symbols:
        path = os.path.join(cache_dir, f"{symbol}.csv")
        if not os.path.exists(path):
            print(f"🛑 Cache missing for {symbol}")
            return True

    # Check if the first symbol's file is stale
    try:
        first_path = os.path.join(cache_dir, f"{symbols[0]}.csv")
        df = pd.read_csv(first_path, parse_dates=["Date"], index_col="Date")
        last_cached_date = pd.to_datetime(df.index.max()).normalize()
        last_trading_day = pd.to_datetime(get_last_trading_day()).normalize()

        if last_cached_date < last_trading_day:
            print(f"📉 Cache is stale: last cached = {last_cached_date}, expected = {last_trading_day}")
            return True
    except Exception as e:
        print(f"⚠️ Error reading cache for {symbols[0]}: {e}")
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
    os.makedirs(cache_dir, exist_ok=True)

    # Load from cache if everything is valid and fresh
    if not is_cache_stale_or_missing(symbols, cache_dir):
        print("✅ Cache is fresh. Loading all symbols locally...")
        result = {}
        for symbol in symbols:
            try:
                path = os.path.join(cache_dir, f"{symbol}.csv")
                df = pd.read_csv(path, parse_dates=["Date"], index_col="Date").sort_index()
                result[symbol] = df
            except Exception as e:
                print(f"⚠️ Failed to load cache for {symbol}: {e}")
        return result

    # Download fresh data
    print(f"📥 Downloading {len(symbols)} symbols from {start} to {end}...")
    try:
        data = yf.download(
            tickers=symbols,
            start=start,
            end=end,
            group_by="ticker",
            auto_adjust=False,
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
            df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]
            df = df.rename_axis("Date").reset_index().set_index("Date").sort_index()
            cached_path = os.path.join(cache_dir, f"{symbol}.csv")

            result[symbol] = df

            if not live_market:
                df.to_csv(cached_path)
        except Exception as e:
            print(f"⚠️ Failed processing {symbol}: {e}")
            os.remove(cached_path) if os.path.exists(cached_path) else None

    return result
