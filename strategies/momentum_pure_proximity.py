import pandas as pd
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator

class MomentumPureProximityStrategy(UniverseStrategy):
    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:

        if not self.is_market_strong(as_of_date):
            return pd.DataFrame(columns=["Symbol", "HighProxScore", "ProxRank", "TotalRank"])

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
            prox_score = ind.high_proximity()

            if None in [prox_score]:
                continue

            data.append({
                "Symbol": symbol,
                "HighProxScore": prox_score
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["ProxRank"] = df["HighProxScore"].rank(ascending=False)
        df["TotalRank"] = df[["ProxRank"]].mean(axis=1)

        return df.sort_values("TotalRank")