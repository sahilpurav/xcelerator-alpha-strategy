import pandas as pd
from core.strategies.template.universe import UniverseStrategy
from utils.indicators import Indicator

class MomentumPriceRsiProximityStrategy(UniverseStrategy):

    def rank_stocks(self, as_of_date: pd.Timestamp) -> pd.DataFrame:
        
        if not self.is_market_strong(as_of_date):
            return pd.DataFrame(columns=["Symbol", "ReturnScore", "RSIScore", "HighProxScore", "ReturnRank", "RSIRank", "ProxRank", "TotalRank"])

        data = []

        for symbol, df in self.price_data.items():
            # Only use data up to this date
            df_subset = df[df.index <= as_of_date]

            # Skip stocks with less than 252 days of data
            if len(df_subset) < 252:
                continue

            # Skip penny stocks and stocks with very high prices
            latest_close = df_subset['Close'].iloc[-1]
            if latest_close < 100 or latest_close > 10000:
                continue

            ind = Indicator(df_subset)

            # Skip stocks with medium traded value less than ₹1 Cr
            traded_value = ind.median_traded_value(22)
            if traded_value is None or traded_value < 1_00_00_000:  # ₹1 Cr
                continue

            # Skip stocks with low average volume
            if ind.avg_volume(22) < 10_000:
                continue

            multi_timeframe_returns = [ind.rtn(22), ind.rtn(44), ind.rtn(66)]
            multi_timeframe_rsi = [ind.rsi(22), ind.rsi(44), ind.rsi(66)]

            if None in multi_timeframe_returns or None in multi_timeframe_rsi:
                continue

            rtn_score = sum(multi_timeframe_returns) / len(multi_timeframe_returns)
            rsi_score = sum(multi_timeframe_rsi) / len(multi_timeframe_rsi)
            prox_score = ind.high_proximity()

            if None in [rtn_score, rsi_score, prox_score]:
                continue

            data.append({
                "Symbol": symbol,
                "ReturnScore": rtn_score,
                "RSIScore": rsi_score,
                "HighProxScore": prox_score
            })

        df = pd.DataFrame(data)

        if df.empty:
            return df

        df["ReturnRank"] = df["ReturnScore"].rank(ascending=False)
        df["RSIRank"] = df["RSIScore"].rank(ascending=False)
        df["ProxRank"] = df["HighProxScore"].rank(ascending=False)

        # Weighted total rank
        df["TotalRank"] = (
            0.8 * df["ReturnRank"] +
            0.1 * df["RSIRank"] +
            0.1 * df["ProxRank"]
        )

        return df.sort_values("TotalRank")
