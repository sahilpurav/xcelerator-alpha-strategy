import pandas as pd

from logic.indicators import (
    calculate_avg_volume,
    calculate_high_proximity,
    calculate_median_traded_value,
    calculate_return,
    calculate_rsi,
)


def rank(
    price_data: dict[str, pd.DataFrame],
    as_of_date: pd.Timestamp,
    weights: tuple[float, float, float] = (0.8, 0.1, 0.1),
    max_affordable_stock_price: float = 10000,
) -> pd.DataFrame:
    """
    Ranks all stocks in the universe using:
    - Multi-timeframe return (22, 44, 66 days)
    - Multi-timeframe RSI (22, 44, 66 days)
    - Proximity to 52-week high

    Applies liquidity and quality filters.
    Returns ranked DataFrame with component scores and ranks.

    Args:
        price_data: Dictionary of symbol -> DataFrame with OHLCV data
        as_of_date: Date for ranking calculation
        weights: Tuple of (return_weight, rsi_weight, proximity_weight) that sum to 1.0
    """

    data = []
    return_weight, rsi_weight, proximity_weight = weights  # Weighted Total Rank

    for symbol, df in price_data.items():
        # Only use data up to the rebalance date
        df = df[df.index <= as_of_date]

        # 1. Must have at least 252 trading days
        if df.shape[0] < 252:
            continue

        latest_close = df["Close"].iloc[-1]

        # Avoiding penny stocks
        if latest_close < 100:
            continue

        # Avoiding stocks that are too expensive based on overall portfolio value
        if latest_close >= max_affordable_stock_price:
            continue

        # 3. Liquidity filters
        if calculate_median_traded_value(df, 22) < 1_00_00_000:
            continue

        if calculate_avg_volume(df, 22) < 10_000:
            continue

        # 4. Calculate composite momentum scores. Do it only if weight > 0 to optimize performance
        returns = (
            [calculate_return(df, d) for d in (22, 44, 66)]
            if return_weight > 0
            else [0, 0, 0]
        )
        rsis = (
            [calculate_rsi(df, d) for d in (22, 44, 66)]
            if rsi_weight > 0
            else [0, 0, 0]
        )
        proximity = calculate_high_proximity(df, 252) if proximity_weight > 0 else 0

        # Skip if any REQUIRED indicator is missing (only check indicators with weight > 0)
        if (
            (return_weight > 0 and any(x is None for x in returns))
            or (rsi_weight > 0 and any(x is None for x in rsis))
            or (proximity_weight > 0 and proximity is None)
        ):
            continue

        return_score = sum(returns) / 3
        rsi_score = sum(rsis) / 3
        proximity_score = proximity

        data.append(
            {
                "symbol": symbol,
                "return_score": return_score,
                "rsi_score": rsi_score,
                "proximity_score": proximity_score,
            }
        )

    # Convert to DataFrame
    df_scores = pd.DataFrame(data)

    if df_scores.empty:
        return df_scores

    # Calculate ranks (lower is better)
    df_scores["return_rank"] = df_scores["return_score"].rank(ascending=False)
    df_scores["rsi_rank"] = df_scores["rsi_score"].rank(ascending=False)
    df_scores["proximity_rank"] = df_scores["proximity_score"].rank(ascending=False)

    df_scores["total_rank"] = (
        return_weight * df_scores["return_rank"]
        + rsi_weight * df_scores["rsi_rank"]
        + proximity_weight * df_scores["proximity_rank"]
    )

    return df_scores.sort_values("total_rank")
