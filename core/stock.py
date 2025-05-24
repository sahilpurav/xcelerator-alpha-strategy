import os
import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, time as dt_time
import pytz

class Stock:
    CACHE_DIR = "cache/stock"
    TEMP_CACHE_DIR = os.path.join(CACHE_DIR, "temp")
    INVALID_SYMBOL_FILE = "cache/stock/invalid_symbols.txt"

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

            india_tz = pytz.timezone("Asia/Kolkata")
            now_ist = datetime.now(india_tz)
            today = pd.Timestamp(now_ist.date())
            today_str = today.strftime('%Y-%m-%d')

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

            # Step 2: Backfill missing data and detect bonus/split
            benchmark_file = os.path.join(cls.CACHE_DIR, "^NSEI.csv")
            if os.path.exists(benchmark_file):
                benchmark_df = pd.read_csv(benchmark_file, parse_dates=['Date'], index_col='Date')
                latest_trading_day = benchmark_df.index.max()
            else:
                latest_trading_day = today  # fallback if benchmark not yet cached
            if last_date < latest_trading_day:
                start_dl = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
                print(f"[info] Fetching data for {symbol} from {start_dl} to {today_str}")
                df = yf.download(
                    symbol,
                    start=start_dl,
                    end=(today + pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
                    progress=False,
                    auto_adjust=True
                )
                if df is not None and not df.empty:
                    df.index = pd.to_datetime(df.index)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

                    # Bonus/Split detection: sudden price drop >30%
                    if not main_df.empty:
                        last_cached_date = main_df.index.max()
                        last_cached_price = main_df.loc[last_cached_date, 'Close']

                        df = df[~df.index.isin(main_df.index)]  # remove overlap

                        if not df.empty:
                            new_price = df['Close'].iloc[0]
                            price_drop = (last_cached_price - new_price) / last_cached_price

                            if price_drop > 0.3:
                                print(f"[adjustment] Bonus/Split detected for {symbol}. Refetching full history.")
                                df = yf.download(symbol, start=start_date, progress=False, auto_adjust=True)
                                if df is not None and not df.empty:
                                    df.index = pd.to_datetime(df.index)
                                    if isinstance(df.columns, pd.MultiIndex):
                                        df.columns = df.columns.get_level_values(0)
                                    df.to_csv(main_cache_file)
                                    return df

                    main_df = pd.concat([main_df, df]).drop_duplicates(keep='last')
                    main_df.to_csv(main_cache_file)

            # Step 3: Fetch today's intraday or final price
            today_already_in_main = today in main_df.index
            df_today = None

            if not today_already_in_main:
                if is_market_open_now:
                    if not os.path.exists(temp_cache_file) or force_refresh:
                        print(f"[info] Fetching today's data for {symbol} from Yahoo Finance")
                        df_today = yf.download(symbol, start=today_str, progress=False, auto_adjust=True)
                        if df_today is not None and not df_today.empty:
                            df_today.index = pd.to_datetime(df_today.index)
                            if isinstance(df_today.columns, pd.MultiIndex):
                                df_today.columns = df_today.columns.get_level_values(0)
                            df_today = df_today[df_today.index.date == today.date()]
                            df_today.to_csv(temp_cache_file)
                    elif os.path.exists(temp_cache_file):
                        df_today = pd.read_csv(temp_cache_file, parse_dates=['Date'], index_col='Date')
                elif is_market_closed_today:
                    print(f"[info] Fetching today's data for {symbol} from Yahoo Finance")
                    df_today = yf.download(symbol, start=today_str, progress=False, auto_adjust=True)
                    if df_today is not None and not df_today.empty:
                        df_today.index = pd.to_datetime(df_today.index)
                        if isinstance(df_today.columns, pd.MultiIndex):
                            df_today.columns = df_today.columns.get_level_values(0)
                        df_today = df_today[df_today.index.date == today.date()]
                        main_df = pd.concat([main_df, df_today]).drop_duplicates(keep='last')
                        main_df.to_csv(main_cache_file)
                        df_today = None
                    if os.path.exists(temp_cache_file):
                        os.remove(temp_cache_file)

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