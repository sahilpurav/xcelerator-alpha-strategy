from core.universe import Universe
from core.stock import Stock
from typing import Dict
import pandas as pd
from core.reporting.backtest_result import BacktestResult
import re
import time
from utils.indicators import Indicator

class UniverseStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.universe_name = config.get("universe", "nifty500")
        self.start_date = config.get("start_date", "2015-01-01")
        self.force_refresh = config.get("force_refresh", False)

        self.raw_symbols, self.yahoo_symbols = Universe.get_symbols(
            self.universe_name,
            force_refresh=self.force_refresh
        )

        self.price_data: Dict[str, pd.DataFrame] = self._load_price_data()

    def _load_price_data(self) -> Dict[str, pd.DataFrame]:
        """
        Downloads and caches historical price data for all stocks in the selected universe.

        This method uses the list of Yahoo-formatted symbols obtained via the Universe class,
        and fetches OHLCV data for each symbol using the Stock class. Data is cached locally
        to avoid repeated downloads on future runs unless `force_refresh=True` is specified
        in the config.

        Returns:
            Dict[str, pd.DataFrame]: A dictionary where the key is the Yahoo Finance symbol
            (e.g., 'RELIANCE.NS') and the value is a pandas DataFrame containing the historical
            price data for that symbol. The DataFrame includes columns like Open, High, Low,
            Close, Adj Close, and Volume, indexed by Date.
        """
        price_data = {}
        for symbol in self.yahoo_symbols:
            # time.sleep(1.5)  # Avoid hitting Yahoo API limits
            df = Stock.get_price(
                symbol,
                start_date=self.start_date,
                force_refresh=self.force_refresh
            )
            if df is not None and not df.empty:
                price_data[symbol] = df

        # Load benchmark symbol (e.g., ^NSEI) if requested
        if self.config.get("load_benchmark", False):
            benchmark_symbol = self.config.get("benchmark", "^NSEI")
            df_benchmark = Stock.get_price(
                benchmark_symbol,
                start_date=self.start_date,
                force_refresh=self.force_refresh
            )
            if df_benchmark is not None and not df_benchmark.empty:
                price_data[benchmark_symbol] = df_benchmark

        return price_data
    
    def is_market_strong(self, as_of_date: pd.Timestamp) -> bool:
        symbol = self.config.get("benchmark", "^NSEI")
        df = self.price_data.get(symbol)
        if df is None:
            return True  # Assume strong if not available

        df_subset = df[df.index <= as_of_date]
        if df_subset.shape[0] < 200:
            return True  # Not enough data

        ind = Indicator(df_subset)
        dma_200 = ind.dma(200)
        latest_close = df_subset["Close"].iloc[-1]

        if dma_200 is None:
            return True

        return latest_close > dma_200
    
    def get_rebalance_dates(self, freq: str = "W") -> list[pd.Timestamp]:
        """
        Generate rebalance dates aligned to available trading days.
        """
        first_symbol = next(iter(self.price_data))
        all_dates = self.price_data[first_symbol].index.to_series()
        rebalance_dates = all_dates.resample(freq).first().dropna().index.tolist()
        return rebalance_dates
    
    def get_price_on_date(self, symbol: str, date: pd.Timestamp) -> float:
        """
        Returns the close price for the given symbol on the specified date.
        Falls back to the nearest previous available date if missing.
        """
        df = self.price_data.get(symbol)
        if df is None or df.empty:
            return None

        if date not in df.index:
            # Use nearest previous date
            df = df[df.index < date]
            if df.empty:
                return None
            return df["Close"].iloc[-1]

        return df.loc[date]["Close"]
    
    def get_return_between(self, symbol: str, from_date: pd.Timestamp, to_date: pd.Timestamp) -> float:
        """
        Calculates the % return for a symbol between two dates using Close prices.
        """
        price_start = self.get_price_on_date(symbol, from_date)
        price_end = self.get_price_on_date(symbol, to_date)

        if price_start is None or price_end is None or price_start == 0:
            return 0.0

        return (price_end - price_start) / price_start
    
    def get_benchmark_curve(self) -> pd.Series:
        """
        Gets benchmark price series using same logic as stock data.
        Rebased to initial capital.
        """
        symbol = self.config.get("benchmark", "^NSEI")
        df = Stock.get_price(symbol, start_date=self.start_date, force_refresh=self.force_refresh)
        if df is None or df.empty:
            raise ValueError(f"Could not fetch benchmark data for {symbol}")

        df = df[df.index >= pd.to_datetime(self.config["backtest_start_date"])]
        rebased = (df["Close"] / df["Close"].iloc[0]) * self.config.get("initial_capital", 1_000_000)
        return rebased

    def run(self, top_n: int = 20):
        """
        Get top N ranked stocks as of the most recent available date.
        """
        latest_date = max(df.index.max() for df in self.price_data.values())
        rankings = self.rank_stocks(as_of_date=latest_date)
        top = rankings.head(top_n).copy()  # Create an explicit copy
        top['Symbol'] = top['Symbol'].str.replace('.NS', '', regex=False)  # Remove '.NS' suffix
        for symbol in top['Symbol'].tolist():
            print(symbol)

    
    def backtest(self, top_n: int = 20, rebalance_frequency: str = "W"):
        """
        Backtest the strategy using the specified parameters.
        """
        start_date = pd.to_datetime(self.config.get("backtest_start_date"))
        initial_capital = self.config.get("initial_capital", 1_000_000)
        rebalance_dates = self.get_rebalance_dates(freq=rebalance_frequency)

        equity_curve = []
        rebalance_log = []
        current_holdings = {}  # symbol -> (qty, buy_price)
        cash = initial_capital

        print(f"\n\U0001f501 Rebalancing top {top_n} stocks from {start_date.date()} every {rebalance_frequency}")

        for i, date in enumerate(rebalance_dates):
            if date < start_date:
                continue

            rankings = self.rank_stocks(as_of_date=date)

            if rankings.empty:
                # Calculate total portfolio value even in cash
                equity_value = 0
                for symbol, (qty, _) in current_holdings.items():
                    price = self.get_price_on_date(symbol, date)
                    if price:
                        equity_value += qty * price
                portfolio_value = equity_value + cash

                rebalance_log.append({
                    "Date": date,
                    "Symbol": "CASH",
                    "Action": "HOLD",
                    "Qty": None,
                    "Price": None,
                    "Value": round(portfolio_value, 2)
                })
                equity_curve.append((date, portfolio_value))
                print(f"➡️ {date.date()} | Market weak, going to cash. Portfolio: ₹{portfolio_value:,.0f}")

                # Liquidate all positions
                current_holdings = {}
                cash = portfolio_value  # carry forward real portfolio value as cash
                continue

            top_symbols = rankings.head(top_n)["Symbol"].tolist()
            print("Top picks:", top_symbols)

            # Sell stocks that are no longer in top N
            new_cash = cash
            for symbol in list(current_holdings.keys()):
                if symbol not in top_symbols:
                    qty, buy_price = current_holdings[symbol]
                    sell_price = self.get_price_on_date(symbol, date)
                    if sell_price:
                        proceeds = qty * sell_price
                        new_cash += proceeds
                        rebalance_log.append({
                            "Date": date,
                            "Symbol": symbol,
                            "Action": "SELL",
                            "Qty": qty,
                            "Price": round(sell_price, 2),
                            "Value": round(proceeds, 2)
                        })
                    del current_holdings[symbol]

            # Buy new stocks with available cash
            slots_available = top_n - len(current_holdings)
            capital_per_stock = new_cash / slots_available if slots_available > 0 else 0

            for symbol in top_symbols:
                if symbol in current_holdings:
                    continue

                price = self.get_price_on_date(symbol, date)
                if price is None or price == 0:
                    continue

                qty = int(capital_per_stock // price)
                cost = qty * price
                if qty > 0:
                    current_holdings[symbol] = (qty, price)
                    new_cash -= cost
                    rebalance_log.append({
                        "Date": date,
                        "Symbol": symbol,
                        "Action": "BUY",
                        "Qty": qty,
                        "Price": round(price, 2),
                        "Value": round(cost, 2)
                    })

            cash = new_cash

            # Compute portfolio value at next rebalance date
            if i + 1 >= len(rebalance_dates):
                break
            next_date = rebalance_dates[i + 1]

            equity_value = 0
            for symbol, (qty, _) in current_holdings.items():
                price = self.get_price_on_date(symbol, next_date)
                if price:
                    equity_value += qty * price

            portfolio_value = equity_value + cash
            equity_curve.append((next_date, portfolio_value))

            prev_value = equity_curve[-2][1] if len(equity_curve) > 1 else initial_capital
            return_pct = (portfolio_value / prev_value) - 1 if prev_value else 0
            print(f"\u27a1\ufe0f {next_date.date()} | Weekly Return: {return_pct:.2%} | Portfolio: ₹{portfolio_value:,.0f}")

        # Finalize results
        equity_series = pd.Series(dict(equity_curve)).sort_index()
        rebalance_df = pd.DataFrame(rebalance_log)
        benchmark_curve = self.get_benchmark_curve()

        result = BacktestResult(
            equity_curve=equity_series,
            rebalance_log=rebalance_df,
            benchmark_curve=benchmark_curve
        )

        portfolio_summary = result.portfolio_summary().iloc[0]
        print("\n\U0001f4caPortfolio Backtest Summary")
        print(f"{'CAGR:':20} {portfolio_summary['CAGR']:.2%}")
        print(f"{'Absolute Return:':20} {portfolio_summary['Absolute Return']:.2%} ({(1 + portfolio_summary['Absolute Return']):.2f}x)")
        print(f"{'Max Drawdown:':20} {portfolio_summary['Max Drawdown']:.2%}")
        print(f"{'Volatility:':20} {portfolio_summary['Volatility']:.2%}")
        print(f"{'Sharpe Ratio:':20} {portfolio_summary['Sharpe Ratio']:.2f}")
        print(f"{'Sortino Ratio:':20} {portfolio_summary['Sortino Ratio']:.2f}")
        print(f"{'Alpha:':20} {portfolio_summary['Alpha']:.2%}" if portfolio_summary['Alpha'] is not None else f"{'Alpha:':20} N/A")
        print(f"{'Avg Churn/Rebalance:':30} {portfolio_summary['Avg Churn/Rebalance']}")
        print(f"{'Avg Holding Period:':30} {portfolio_summary['Avg Holding Period']} rebalances")

        benchmark_summary = result.benchmark_summary()
        if not benchmark_summary.empty:
            bm = benchmark_summary.iloc[0]
            print("\n\U0001f4c8Benchmark Backtest Summary")
            print(f"{'CAGR:':20} {bm['CAGR']:.2%}")
            print(f"{'Absolute Return:':20} {bm['Absolute Return']}")
            print(f"{'Max Drawdown:':20} {bm['Max Drawdown']:.2%}")
            print(f"{'Volatility:':20} {bm['Volatility']:.2%}")

        strategy_classname = re.sub(r'(?<!^)(?=[A-Z])', '_', self.__class__.__name__).lower()
        result.to_csv(f"reports/{strategy_classname}/")
