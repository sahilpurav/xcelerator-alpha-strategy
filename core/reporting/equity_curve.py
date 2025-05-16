import pandas as pd

class EquityCurveSimulator:
    @staticmethod
    def simulate(
        rebalance_log: pd.DataFrame,
        price_data: dict[str, pd.DataFrame],
        nsei_data: pd.DataFrame,
        initial_capital: float
    ) -> pd.Series:
        """
        Simulate daily equity curve using rebalance log and price data,
        anchored on NSEI trading calendar.
        """
        rebalance_log = rebalance_log.sort_values("Date")
        rebalance_by_date = rebalance_log.groupby("Date")

        portfolio = {}
        cash = initial_capital
        equity_curve = {}

        backtest_start = rebalance_log["Date"].min()
        trading_days = nsei_data[nsei_data.index >= backtest_start].index
        for date in trading_days:
            # Apply trades (if any) on this date
            if date in rebalance_by_date.groups:
                group = rebalance_by_date.get_group(date)

                # If going to cash, clear the portfolio
                if (group["Symbol"] == "CASH").all():
                    portfolio.clear()
                    # Optional: also set cash to the last value recorded, just to be safe
                    value_col = group["Value"].dropna()
                    if not value_col.empty:
                        cash = value_col.values[-1]
                else:
                    for _, row in group.iterrows():
                        symbol, action, qty, price = row["Symbol"], row["Action"], row["Qty"], row["Price"]
                        if pd.isna(qty) or pd.isna(price):
                            continue

                        qty = int(qty)
                        if action == "BUY":
                            portfolio[symbol] = portfolio.get(symbol, 0) + qty
                            cash -= qty * price
                        elif action == "SELL":
                            if symbol in portfolio:
                                cash += qty * price
                                portfolio[symbol] -= qty
                                if portfolio[symbol] <= 0:
                                    del portfolio[symbol]


            # Compute total portfolio value
            value = cash
            has_valid_price = False

            for symbol, qty in portfolio.items():
                df = price_data.get(symbol)
                if df is not None and date in df.index and pd.notna(df.loc[date, "Close"]):
                    value += qty * df.loc[date, "Close"]
                    has_valid_price = True

            # If portfolio contains stocks but no valid prices were found, retain previous value
            if not has_valid_price and len(portfolio) > 0:
                if len(equity_curve) > 0:
                    equity_curve[date] = list(equity_curve.values())[-1]
                else:
                    equity_curve[date] = initial_capital
            else:
                equity_curve[date] = value

        return pd.Series(equity_curve).sort_index()
