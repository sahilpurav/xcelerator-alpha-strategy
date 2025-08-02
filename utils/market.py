from functools import lru_cache
import requests

import pandas as pd
from datetime import datetime, timedelta

from logic.indicators import calculate_dma, calculate_ema


@lru_cache(maxsize=1)
def get_market_status() -> dict:
    """
    Fetches market status from NSE API to check if market is open and get trade date.
    Returns a dict with 'marketStatus' and 'tradeDate' keys.
    """
    try:
        url = "https://www.nseindia.com/api/marketStatus"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle different response formats
        if isinstance(data.get("marketState"), dict):
            capital_market = data.get("marketState", {}).get("Capital Market", {})
        elif isinstance(data.get("marketState"), list):
            # If marketState is a list, find the Capital Market entry
            capital_market = {}
            for market in data.get("marketState", []):
                if isinstance(market, dict) and market.get("market") == "Capital Market":
                    capital_market = market
                    break
        else:
            capital_market = {}
        
        return {
            "marketStatus": capital_market.get("marketStatus", "CLOSED"),
            "tradeDate": capital_market.get("tradeDate", "")
        }
    except Exception as e:
        print(f"⚠️ Failed to fetch market status: {e}")
        # Default to closed if API fails
        return {"marketStatus": "Closed", "tradeDate": ""}


def get_last_trading_date() -> str:
    """
    Returns the last trading day as a string in YYYY-MM-DD format
    using available data from NSE's market status API.
    """
    market_status = get_market_status()
    trade_date = market_status["tradeDate"]

    # The value for tradeDate is in "01-Aug-2025 15:30" format
    # Convert the trade date to YYYY-MM-DD pandas format
    return pd.to_datetime(trade_date).strftime("%Y-%m-%d")


def get_ranking_date(day_of_week: str = None) -> str:
    """
    Returns the most recent specified weekday (e.g., Wednesday) that was a trading day.
    Uses Zerodha API to fetch Nifty 50 index data for the last 14 days.
    If no trading day is found for the specified weekday in the last 14 days,
    returns the most recent trading day before that.

    Args:
        day_of_week: Day name (Monday, Tuesday, etc.) or None for today

    Returns:
        Date string in YYYY-MM-DD format
    """
    if day_of_week is None:
        # If no specific day is requested, return the last trading date
        return get_last_trading_date()

    # Validate day_of_week
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if day_of_week not in valid_days:
        raise ValueError(
            f"Invalid day_of_week: {day_of_week}. Must be one of {valid_days}"
        )

    try:
        # Import here to avoid circular imports
        from broker.zerodha import ZerodhaBroker
        
        # Initialize Zerodha broker
        broker = ZerodhaBroker()
        kite = broker.kite
        instrument_token_map = broker.get_instrument_token_map()
        
        # Use Nifty 50 index symbol for trading day detection
        nifty50_symbol = "NIFTY 50"
        
        if nifty50_symbol not in instrument_token_map:
            print(f"⚠️ {nifty50_symbol} not found in instrument token map, using last trading date")
            return get_last_trading_date()
        
        instrument_token = instrument_token_map[nifty50_symbol]
        
        # Calculate date range for last 14 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=20)  # Extra buffer to ensure we get 14 trading days
        
        # Fetch historical data from Kite
        historical_data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=start_date,
            to_date=end_date,
            interval="day"
        )
        
        if not historical_data:
            print("⚠️ No historical data received from Zerodha, using last trading date")
            return get_last_trading_date()
        
        # Convert to DataFrame and extract dates
        df = pd.DataFrame(historical_data)
        df["date"] = pd.to_datetime(df["date"])
        
        # Get unique trading dates and sort them
        trading_dates = df["date"].dt.date.unique()
        trading_dates = sorted(trading_dates, reverse=True)  # Most recent first
        
        # Get mapping of day name to day number (0=Monday, 4=Friday)
        day_to_num = {d: i for i, d in enumerate(valid_days)}
        target_day_num = day_to_num[day_of_week]
        
        # Find the most recent occurrence of the target day that has data
        for date in trading_dates:
            if pd.to_datetime(date).weekday() == target_day_num:
                return date.strftime("%Y-%m-%d")
        
        # If no matching day found, return the most recent trading date
        return trading_dates[0].strftime("%Y-%m-%d")
        
    except Exception as e:
        print(f"⚠️ Error fetching ranking date from Zerodha: {e}")
        # Fallback to last trading date
        return get_last_trading_date()


def is_market_strong(
    price_data: dict[str, pd.DataFrame],
    benchmark_symbol: str,
    as_of_date: pd.Timestamp = None,
    breadth_threshold: float = 0.4
) -> bool:
    """
    Determines if the market is strong based on benchmark index and market breadth.

    Market is weak if ANY of the below conditions are met:
    1. Benchmark price is below 22, 44, AND 66 DMA (all three conditions)
    2. Market breadth ratio is below the threshold

    Args:
        price_data (dict): Dictionary of symbol -> OHLCV DataFrame (must include benchmark symbol)
        benchmark_symbol (str): Symbol for benchmark index (e.g., "NIFTY 500", "NIFTY 100")
        as_of_date (pd.Timestamp, optional): Date to calculate metrics for
        breadth_threshold (float): Minimum breadth ratio required (default: 0.4 = 40%)

    Returns:
        bool: True if the market is strong, False otherwise.
    """
    # Get benchmark data from price_data
    benchmark_df = price_data.get(benchmark_symbol)
    if benchmark_df is None:
        raise ValueError(
            f"Benchmark data ({benchmark_symbol}) not found in price_data."
        )

    # Filter benchmark data up to as_of_date if provided
    if as_of_date is not None:
        # Make an explicit copy to avoid SettingWithCopyWarning
        benchmark_df = benchmark_df[benchmark_df.index <= as_of_date].copy()
    else:
        # Still make a copy to be safe
        benchmark_df = benchmark_df.copy()

    if benchmark_df.shape[0] < 66:
        return False

    # Ensure Close column is numeric
    benchmark_df["Close"] = pd.to_numeric(benchmark_df["Close"], errors="coerce")

    latest_close = benchmark_df["Close"].iloc[-1]
    ema_22 = calculate_ema(benchmark_df, 22)
    ema_44 = calculate_ema(benchmark_df, 44)
    ema_66 = calculate_ema(benchmark_df, 66)

    if ema_22 is None or ema_44 is None or ema_66 is None or pd.isna(latest_close):
        print("⚠️ Could not calculate EMAs or latest close price is invalid.")
        return False

    # Ensure all values are numeric before comparison
    try:
        latest_close = float(latest_close)
        ema_22 = float(ema_22)
        ema_44 = float(ema_44)
        ema_66 = float(ema_66)
    except (ValueError, TypeError):
        print("⚠️ Non-numeric values detected when checking market strength.")
        return False

    # Check benchmark condition: Market is weak if price is below ALL EMAs
    benchmark_weak = sum(latest_close < ema for ema in [ema_22, ema_44, ema_66]) == 3

    if benchmark_weak:
        print("⚠️ Market is weak (benchmark below All EMAs), skipping ranking.")
        return False

    # Check market breadth
    breadth_ratio = _get_market_breadth_ratio(
        price_data, dma_period=44, as_of_date=as_of_date
    )

    if breadth_ratio < breadth_threshold:
        print(
            f"Market breadth is weak ({breadth_ratio:.2%} < {breadth_threshold:.0%}), skipping ranking."
        )
        return False

    print(
        f"💪 Market is strong: Benchmark above EMAs and breadth ratio is {breadth_ratio:.2%}."
    )
    return True


def _get_market_breadth_ratio(
    price_data: dict[str, pd.DataFrame],
    dma_period: int = 44,
    as_of_date: pd.Timestamp = None,
) -> float:
    """
    Calculates the percentage of stocks trading above their n-day DMA as of a specific date.
    Excludes benchmark indices (symbols starting with ^) from the calculation.

    Args:
        price_data: Dictionary of symbol -> OHLCV DataFrame
        dma_period: DMA period to use (e.g., 50, 200)
        as_of_date: Date to calculate the ratio for (if None, uses latest available data)

    Returns:
        float: Ratio of stocks above their DMA (between 0.0 and 1.0)
    """
    count_above_dma = 0
    total = 0

    for symbol, df in price_data.items():
        # Skip benchmark data
        if symbol.startswith("^"):
            continue

        # Filter data up to the as_of_date if provided
        if as_of_date is not None:
            df = df[df.index <= as_of_date]

        if df.shape[0] < dma_period:
            continue

        dma = calculate_dma(df, dma_period)
        if dma is None:
            continue

        # Use the latest close price in the filtered dataframe (as of the specified date)
        current_price = df["Close"].iloc[-1]
        if current_price > dma:
            count_above_dma += 1

        total += 1

    return count_above_dma / total if total > 0 else 0.0
