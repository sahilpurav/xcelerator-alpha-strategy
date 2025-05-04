# utils/indicators.py

import pandas as pd

class Indicator:
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with a price DataFrame containing at least a 'Close' column.
        """
        self.df = df

    def rtn(self, n: int) -> float:
        """
        Calculates the return over the past n days.

        Args:
            n (int): Lookback period in trading days.

        Returns:
            float: Return percentage or None if not enough data.
        """
        if self.df.shape[0] < n:
            return None

        recent = self.df["Close"].iloc[-1]
        past = self.df["Close"].iloc[-n]

        return ((recent - past) / past) * 100

    def rsi(self, period: int = 14) -> float:
        """
        Calculates RSI using Wilder's method.

        Args:
            period (int): Number of days to calculate RSI over

        Returns:
            float: RSI value or None if not enough data
        """
        if self.df.shape[0] < period + 1:
            return None

        delta = self.df["Close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=period).mean().iloc[-1]
        avg_loss = loss.rolling(window=period).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0  # Max RSI

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def high_proximity(self, lookback: int = 252) -> float:
        """
        Calculates proximity to the highest close in the last `lookback` days.

        Args:
            lookback (int): Number of trading days to look back (default 252 ~ 1 year)

        Returns:
            float: Proximity percentage or None if not enough data
        """
        if self.df.shape[0] < lookback:
            return None

        current = self.df["Close"].iloc[-1]
        highest = self.df["Close"].iloc[-lookback:].max()

        return (current / highest) * 100
