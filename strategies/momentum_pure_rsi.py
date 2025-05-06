from core.reporting.backtest_result import BacktestResult
import pandas as pd
import numpy as np
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator

class MomentumPureRsi(UniverseStrategy):
    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:
        data = []

        for symbol, df in self.price_data.items():
            # Only use data up to this date
            df_subset = df[df.index <= as_of_date]

            # Skip stocks with price less than 100
            if df_subset.empty or df_subset['Close'].iloc[-1] < 100:
                continue

            ind = Indicator(df_subset)

            multi_timeframe_rsi = [ind.rsi(22), ind.rsi(44), ind.rsi(66)]

            if None in multi_timeframe_rsi:
                continue

            rsi_score = sum(multi_timeframe_rsi) / len(multi_timeframe_rsi)

            if None in [rsi_score]:
                continue

            data.append({
                "Symbol": symbol,
                "RSIScore": rsi_score,
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["TotalRank"] = df["RSIScore"].rank(ascending=False)

        return df.sort_values("TotalRank")
