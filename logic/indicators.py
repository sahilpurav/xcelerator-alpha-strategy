import pandas as pd

def calculate_return(df: pd.DataFrame, days: int) -> float:
    """
    Calculates percentage return over the last `days` period using 'Close' prices.

    Returns:
        float: Return percentage or None if insufficient data
    """
    if df.shape[0] < days:
        return None

    recent = df["Close"].iloc[-1]
    past = df["Close"].iloc[-days]

    return ((recent - past) / past) * 100


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculates the Relative Strength Index (RSI) over the given `period`.

    Returns:
        float: RSI value (0 to 100) or None if insufficient data
    """
    if df.shape[0] < period + 1:
        return None

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period).mean().iloc[-1]
    avg_loss = loss.rolling(window=period).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0  # RSI is 100 when there's no loss

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_dma(df: pd.DataFrame, period: int = 200) -> float:
    """
    Calculates the n-day Simple Moving Average (DMA) using 'Close' prices.

    Returns:
        float: DMA value or None if insufficient data
    """
    if df.shape[0] < period:
        return None

    return df["Close"].rolling(window=period).mean().iloc[-1]


def calculate_high_proximity(df: pd.DataFrame, lookback: int = 252) -> float:
    """
    Calculates proximity to the highest close in the last `lookback` days.

    Returns:
        float: Proximity as a percentage (100 = at high, <100 = below)
    """
    if df.shape[0] < lookback:
        return None

    current = df["Close"].iloc[-1]
    highest = df["Close"].iloc[-lookback:].max()

    return (current / highest) * 100


def calculate_avg_volume(df: pd.DataFrame, window: int = 22) -> float:
    """
    Calculates average volume over the given rolling window.

    Returns:
        float: Average volume or None if insufficient data
    """
    if df.shape[0] < window:
        return None

    return df["Volume"].tail(window).mean()


def calculate_median_traded_value(df: pd.DataFrame, window: int = 22) -> float:
    """
    Calculates the median traded value (Volume × Close) over a rolling window.

    Returns:
        float: Median traded value or None if insufficient data
    """
    if df.shape[0] < window:
        return None

    traded_value = df["Close"] * df["Volume"]
    return traded_value.tail(window).median()
