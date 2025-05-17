from core.reporting.backtest_result import BacktestResult
import pandas as pd
import numpy as np
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator
import os
import pickle

class MomentumRsiProximityStrategy(UniverseStrategy):
    
    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:
        
        if not self.is_market_strong(as_of_date):
            return pd.DataFrame(columns=["Symbol", "RSIScore", "HighProxScore", "RSIRank", "ProxRank", "TotalRank"])

        data = []

        for symbol, df in self.price_data.items():
            # Only use data up to this date
            df_subset = df[df.index <= as_of_date]

            # Skip stocks with price less than 100
            if df_subset.empty or df_subset['Close'].iloc[-1] < 100:
                continue

            # Skip stocks with less than 252 days of data
            if len(df_subset) < 252:
                continue

            # Skip stocks with price greater than 10000
            if df_subset.empty or df_subset['Close'].iloc[-1] > 10000:
                continue

            ind = Indicator(df_subset)

            multi_timeframe_rsi = [ind.rsi(22), ind.rsi(44), ind.rsi(66)]

            if None in multi_timeframe_rsi:
                continue

            rsi_score = sum(multi_timeframe_rsi) / len(multi_timeframe_rsi)
            prox_score = ind.high_proximity()

            if None in [rsi_score, prox_score]:
                continue

            data.append({
                "Symbol": symbol,
                "RSIScore": rsi_score,
                "HighProxScore": prox_score
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["RSIRank"] = df["RSIScore"].rank(ascending=False)
        df["ProxRank"] = df["HighProxScore"].rank(ascending=False)
        df["TotalRank"] = df[["RSIRank", "ProxRank"]].mean(axis=1)

        return df.sort_values("TotalRank")
