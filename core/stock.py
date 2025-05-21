import os
import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta, time as dt_time
import pytz

class Stock:
    CACHE_DIR = "cache/stock"
    TEMP_CACHE_DIR = os.path.join(CACHE_DIR, "temp")
    INVALID_SYMBOL_FILE = "cache/stock/invalid_symbols.txt"
    ASM_SYMBOL_FILE = "cache/asm.csv"

    @staticmethod
    def is_market_open_now() -> bool:
        india_tz = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(india_tz)
        market_open = dt_time(9, 15)
        market_close = dt_time(15, 30)
        return now_ist.weekday() < 5 and market_open <= now_ist.time() < market_close

    @classmethod
    def get_price(cls, symbol: str, start_date: str = "2015-01-01", force_refresh: bool = False) -> Optional[pd.DataFrame]:
        try:
            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            os.makedirs(cls.TEMP_CACHE_DIR, exist_ok=True)

            main_cache_file = os.path.join(cls.CACHE_DIR, f"{symbol}.csv")
            temp_cache_file = os.path.join(cls.TEMP_CACHE_DIR, f"{symbol}.csv")

            today = pd.Timestamp(datetime.now().date())
            yesterday = today - pd.Timedelta(days=1)
            is_market_open = cls.is_market_open_now()

            # Step 1: Load main cache
            if not force_refresh and os.path.exists(main_cache_file):
                main_df = pd.read_csv(main_cache_file, parse_dates=['Date'], index_col='Date')
                last_date = main_df.index.max()
            else:
                main_df = pd.DataFrame()
                last_date = pd.Timestamp(start_date) - pd.Timedelta(days=1)

            # Step 2: Backfill up to yesterday if needed
            if last_date < yesterday:
                start_dl = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"[main update] Fetching {symbol} from {start_dl} to {yesterday.date()}")
                df = yf.download(symbol, start=start_dl, end=today.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)

                if df is not None and not df.empty:
                    df.index = pd.to_datetime(df.index)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

                    combined = pd.concat([main_df, df])
                    combined = combined[~combined.index.duplicated(keep='last')]
                    combined.to_csv(main_cache_file)
                    main_df = combined

            # Step 3: Fetch today's price into temp cache if market open
            if is_market_open:
                if not os.path.exists(temp_cache_file) or force_refresh:
                    print(f"[temp update] Fetching today's price for {symbol}")
                    df_today = yf.download(symbol, start=today.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)

                    if df_today is not None and not df_today.empty:
                        df_today.index = pd.to_datetime(df_today.index)
                        if isinstance(df_today.columns, pd.MultiIndex):
                            df_today.columns = df_today.columns.get_level_values(0)
                        df_today = df_today[df_today.index.date == today.date()]
                        df_today.to_csv(temp_cache_file)
                else:
                    df_today = pd.read_csv(temp_cache_file, parse_dates=['Date'], index_col='Date')
            else:
                df_today = None
                if os.path.exists(temp_cache_file):
                    os.remove(temp_cache_file)

            # Step 4: Return merged data
            if df_today is not None and not df_today.empty:
                full_df = pd.concat([main_df, df_today])
                full_df = full_df[~full_df.index.duplicated(keep='last')]
                return full_df

            return main_df

        except Exception as e:
            print(f"[error] Failed to get price for {symbol}: {e}")
            cls._record_invalid_symbol(symbol)
            return None
        
    @staticmethod
    def _record_invalid_symbol(symbol: str):
        if symbol.startswith("^"):
            return  # Don't mark index symbols like ^NSEI as invalid
        
        os.makedirs("cache", exist_ok=True)
        with open(Stock.INVALID_SYMBOL_FILE, "a") as f:
            f.write(symbol + "\n")