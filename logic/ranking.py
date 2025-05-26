import pandas as pd
from logic.indicators import (
    calculate_return,
    calculate_rsi,
    calculate_high_proximity,
    calculate_avg_volume,
    calculate_median_traded_value
)

def rank(price_data: dict[str, pd.DataFrame], as_of_date: pd.Timestamp) -> pd.DataFrame:
    """
    Ranks all stocks in the universe using:
    - Multi-timeframe return (22, 44, 66 days)
    - Multi-timeframe RSI (22, 44, 66 days)
    - Proximity to 52-week high

    Applies liquidity and quality filters.
    Returns ranked DataFrame with component scores and ranks.
    """

    data = []

    for symbol, df in price_data.items():
        # Only use data up to the rebalance date
        df = df[df.index <= as_of_date]

        # 1. Must have at least 252 trading days
        if df.shape[0] < 252:
            continue

        # 2. Price filter: ₹100 < Close < ₹10,000
        latest_close = df["Close"].iloc[-1]
        if latest_close < 100 or latest_close > 10000:
            continue

        # 3. Liquidity filters
        if calculate_median_traded_value(df, 22) < 1_00_00_000:
            continue

        if calculate_avg_volume(df, 22) < 10_000:
            continue

        # 4. Calculate composite momentum scores
        returns = [calculate_return(df, d) for d in (22, 44, 66)]
        rsis = [calculate_rsi(df, d) for d in (22, 44, 66)]
        proximity = calculate_high_proximity(df, 252)

        # Skip if any indicator is missing
        if any(x is None for x in returns + rsis) or proximity is None:
            continue

        return_score = sum(returns) / 3
        rsi_score = sum(rsis) / 3
        proximity_score = proximity

        data.append({
            "symbol": symbol,
            "return_score": return_score,
            "rsi_score": rsi_score,
            "proximity_score": proximity_score
        })

    # Convert to DataFrame
    df_scores = pd.DataFrame(data)

    if df_scores.empty:
        return df_scores

    # Calculate ranks (lower is better)
    df_scores["return_rank"] = df_scores["return_score"].rank(ascending=False)
    df_scores["rsi_rank"] = df_scores["rsi_score"].rank(ascending=False)
    df_scores["proximity_rank"] = df_scores["proximity_score"].rank(ascending=False)

    # Weighted Total Rank
    df_scores["total_rank"] = (
        0.8 * df_scores["return_rank"] +
        0.1 * df_scores["rsi_rank"] +
        0.1 * df_scores["proximity_rank"]
    )

    return df_scores.sort_values("total_rank")