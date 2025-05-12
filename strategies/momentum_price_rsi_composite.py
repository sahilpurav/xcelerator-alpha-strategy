from core.reporting.backtest_result import BacktestResult
import pandas as pd
import numpy as np
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator

class MomentumPriceRsiComposite(UniverseStrategy):
    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:
        
        if not self.is_market_strong(as_of_date):
            return pd.DataFrame(columns=["Symbol", "ReturnScore", "RSIScore", "ReturnRank", "RSIRank", "TotalRank"])

        data = []

        for symbol, df in self.price_data.items():
            # Only use data up to this date
            df_subset = df[df.index <= as_of_date]

            # Skip stocks with price less than 100
            if df_subset.empty or df_subset['Close'].iloc[-1] < 100:
                continue

            # Skip stocks with price greater than 10000
            if df_subset.empty or df_subset['Close'].iloc[-1] > 10000:
                continue

            ind = Indicator(df_subset)

            multi_timeframe_returns = [ind.rtn(22), ind.rtn(44), ind.rtn(66)]
            multi_timeframe_rsi = [ind.rsi(22), ind.rsi(44), ind.rsi(66)]

            if None in multi_timeframe_returns or None in multi_timeframe_rsi:
                continue

            rtn_score = sum(multi_timeframe_returns) / len(multi_timeframe_returns)
            rsi_score = sum(multi_timeframe_rsi) / len(multi_timeframe_rsi)

            if None in [rtn_score, rsi_score]:
                continue

            data.append({
                "Symbol": symbol,
                "ReturnScore": rtn_score,
                "RSIScore": rsi_score,
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["ReturnRank"] = df["ReturnScore"].rank(ascending=False)
        df["RSIRank"] = df["RSIScore"].rank(ascending=False)
        df["TotalRank"] = df[["ReturnRank", "RSIScore"]].mean(axis=1)

        return df.sort_values("TotalRank")
