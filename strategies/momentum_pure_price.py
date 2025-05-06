from core.reporting.backtest_result import BacktestResult
import pandas as pd
import numpy as np
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator

class MomentumPurePrice(UniverseStrategy):
    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:
        data = []

        for symbol, df in self.price_data.items():
            # Only use data up to this date
            df_subset = df[df.index <= as_of_date]

            # Skip stocks with price less than 100
            if df_subset.empty or df_subset['Close'].iloc[-1] < 100:
                continue

            ind = Indicator(df_subset)

            multi_timeframe_returns = [ind.rtn(22), ind.rtn(44), ind.rtn(66)]

            if None in multi_timeframe_returns:
                continue

            rtn_score = sum(multi_timeframe_returns) / len(multi_timeframe_returns)

            if None in [rtn_score]:
                continue

            data.append({
                "Symbol": symbol,
                "ReturnScore": rtn_score,
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["TotalRank"] = df["ReturnScore"].rank(ascending=False)

        return df.sort_values("TotalRank")
