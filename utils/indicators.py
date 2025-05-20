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
    
    def dma(self, period: int = 200) -> float:
        """
        Calculates the n-day Simple Moving Average (e.g., 200 DMA) on Close price.

        Args:
            period (int): Number of days for the moving average

        Returns:
            float: Moving average value or None if not enough data
        """
        if self.df.shape[0] < period:
            return None

        return self.df["Close"].rolling(window=period).mean().iloc[-1]
    
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
    
    def avg_traded_value(self, period: int = 22) -> float:
        """
        Calculates the average traded value (volume × close) over the given period.

        Args:
            period (int): Lookback period in trading days.

        Returns:
            float: Average traded value in ₹ or None if insufficient data.
        """
        if self.df.shape[0] < period:
            return None

        avg_volume = self.df["Volume"].iloc[-period:].mean()
        avg_close = self.df["Close"].iloc[-period:].mean()

        return avg_volume * avg_close
    
    def avg_volume(self, window=22):
        """
        Calculates the average volume over the given window.
        """
        try:
            if self.df.shape[0] < window:
                return None
            return self.df["Volume"].tail(window).mean()
        except Exception:
            return None
        
    def median_traded_value(self, window=22):
        """
        Calculates the median traded value (volume × close) over the given window.
        """
        try:
            if self.df.shape[0] < window:
                return None
            traded_value = self.df["Close"] * self.df["Volume"]
            return traded_value.tail(window).median()
        except Exception:
            return None