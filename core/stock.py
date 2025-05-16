import os
import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta

class Stock:
    CACHE_DIR = "cache/stock"
    INVALID_SYMBOL_FILE = "cache/stock/invalid_symbols.txt"
    ASM_SYMBOL_FILE = "cache/asm.csv"

    @classmethod
    def get_price(cls, symbol: str, start_date: str = "2015-01-01", force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        Fetches and caches historical price data from Yahoo Finance.

        Args:
            symbol (str): Yahoo symbol, e.g., 'RELIANCE.NS'
            start_date (str): e.g., '2015-01-01'
            force_refresh (bool): If True, forces re-download from Yahoo

        Returns:
            pd.DataFrame: Historical OHLCV data
        """
        # Placeholder for actual implementation
        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(cls.CACHE_DIR, f"{symbol}.csv")

        if not force_refresh and os.path.exists(cache_file):
            try:
                cached_data = pd.read_csv(cache_file, parse_dates=['Date'], index_col='Date')
                last_date = cached_data.index.max()

                # Check if the last date is today
                today = pd.Timestamp(datetime.now().date())
                weekday = today.weekday()
                if last_date >= today or (weekday in [5, 6] and last_date >= today - pd.Timedelta(days=weekday - 4)):
                    return cached_data
                
                # Fetch only missing data
                start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"[updating] Fetching missing data for {symbol} from {start_date}...")
                new_data = yf.download(symbol, start=start_date, progress=False, auto_adjust=True)

                if new_data is not None and not new_data.empty:
                    new_data.index = pd.to_datetime(new_data.index)
                    if isinstance(new_data.columns, pd.MultiIndex):
                        new_data.columns = new_data.columns.get_level_values(0)

                    # Append new data to cached data
                    updated_data = pd.concat([cached_data, new_data])
                    updated_data = updated_data[~updated_data.index.duplicated(keep='last')]  # Remove duplicates
                    updated_data.to_csv(cache_file)
                    return updated_data
                else:
                    print(f"[warning] No new data found for {symbol}")
                    return cached_data
            except Exception as e:
                print(f"[warning] Could not read cache for {symbol}: {e}")
                os.remove(cache_file)

        try:
            print(f"[fetching] Downloading {symbol} from Yahoo Finance...")
            df = yf.download(symbol, start=start_date, progress=False, auto_adjust=True)

            if df is None or df.empty:
                print(f"[warning] No data found for {symbol}")
                cls._record_invalid_symbol(symbol)
                return None

            # ✅ Ensure index is datetime
            df.index = pd.to_datetime(df.index)

            # Handle multi-index columns (flatten if necessary)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Save to CSV with Date as column, return with DatetimeIndex
            df_to_save = df.copy().reset_index()
            df_to_save.columns.name = None
            df_to_save.to_csv(cache_file, index=False)

            return df

        except Exception as e:
            print(f"[error] Failed to fetch {symbol}: {e}")
            cls._record_invalid_symbol(symbol)
            return None
        
    @staticmethod
    def _record_invalid_symbol(symbol: str):
        if symbol.startswith("^"):
            return  # Don't mark index symbols like ^NSEI as invalid
        
        os.makedirs("cache", exist_ok=True)
        with open(Stock.INVALID_SYMBOL_FILE, "a") as f:
            f.write(symbol + "\n")