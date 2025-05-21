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
            import pytz
            from datetime import datetime, timedelta, time as dt_time

            os.makedirs(cls.CACHE_DIR, exist_ok=True)
            os.makedirs(cls.TEMP_CACHE_DIR, exist_ok=True)

            main_cache_file = os.path.join(cls.CACHE_DIR, f"{symbol}.csv")
            temp_cache_file = os.path.join(cls.TEMP_CACHE_DIR, f"{symbol}.csv")

            india_tz = pytz.timezone("Asia/Kolkata")
            now_ist = datetime.now(india_tz)
            today = pd.Timestamp(now_ist.date())
            today_str = today.strftime('%Y-%m-%d')
            yesterday = today - pd.Timedelta(days=1)

            market_open = dt_time(9, 15)
            market_close = dt_time(15, 30)
            is_weekday = now_ist.weekday() < 5
            is_market_open_now = is_weekday and market_open <= now_ist.time() < market_close
            is_market_closed_today = is_weekday and now_ist.time() >= dt_time(15, 31)

            # Step 1: Load main cache
            if not force_refresh and os.path.exists(main_cache_file):
                main_df = pd.read_csv(main_cache_file, parse_dates=['Date'], index_col='Date')
                last_date = main_df.index.max()
            else:
                main_df = pd.DataFrame()
                last_date = pd.Timestamp(start_date) - pd.Timedelta(days=1)

            # Step 2: Backfill up to yesterday
            if last_date < yesterday:
                start_dl = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"[main update] Fetching {symbol} from {start_dl} to {yesterday.date()}")
                df = yf.download(symbol, start=start_dl, end=today_str, progress=False, auto_adjust=True)
                if df is not None and not df.empty:
                    df.index = pd.to_datetime(df.index)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    main_df = pd.concat([main_df, df]).drop_duplicates(keep='last')
                    main_df.to_csv(main_cache_file)

            # Step 3: Fetch today's data based on market hours
            today_already_in_main = today in main_df.index

            if not today_already_in_main:
                if is_market_open_now:
                    if not os.path.exists(temp_cache_file) or force_refresh:
                        print(f"[temp update] Fetching intraday price for {symbol}")
                        df_today = yf.download(symbol, start=today_str, progress=False, auto_adjust=True)
                        if df_today is not None and not df_today.empty:
                            df_today.index = pd.to_datetime(df_today.index)
                            if isinstance(df_today.columns, pd.MultiIndex):
                                df_today.columns = df_today.columns.get_level_values(0)
                            df_today = df_today[df_today.index.date == today.date()]
                            df_today.to_csv(temp_cache_file)
                    elif os.path.exists(temp_cache_file):
                        df_today = pd.read_csv(temp_cache_file, parse_dates=['Date'], index_col='Date')
                    else:
                        df_today = None
                elif is_market_closed_today:
                    print(f"[main update] Fetching today's final price for {symbol}")
                    df_today = yf.download(symbol, start=today_str, progress=False, auto_adjust=True)
                    if df_today is not None and not df_today.empty:
                        df_today.index = pd.to_datetime(df_today.index)
                        if isinstance(df_today.columns, pd.MultiIndex):
                            df_today.columns = df_today.columns.get_level_values(0)
                        df_today = df_today[df_today.index.date == today.date()]
                        main_df = pd.concat([main_df, df_today]).drop_duplicates(keep='last')
                        main_df.to_csv(main_cache_file)
                        df_today = None  # already merged
                    if os.path.exists(temp_cache_file):
                        os.remove(temp_cache_file)
                else:
                    df_today = None
            else:
                df_today = None

            # Step 4: Merge and return
            if df_today is not None and not df_today.empty:
                full_df = pd.concat([main_df, df_today]).drop_duplicates(keep='last')
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