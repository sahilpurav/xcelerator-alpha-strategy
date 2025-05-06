from core.universe import Universe
from core.stock import Stock
from typing import Dict
import pandas as pd
from core.reporting.backtest_result import BacktestResult
import re
import time

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
            time.sleep(1.5)  # Avoid hitting Yahoo API limits
            df = Stock.get_price(
                symbol,
                start_date=self.start_date,
                force_refresh=self.force_refresh
            )
            if df is not None and not df.empty:
                price_data[symbol] = df
        return price_data
    
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
        top = rankings.head(top_n)
        print(top)

    
    def backtest(self, top_n: int = 20, rebalance_frequency: str = "W"):
        """
        Backtest scaffold: print rebalance dates and prepare equity curve.
        """
        start_date = pd.to_datetime(self.config.get("backtest_start_date"))
        portfolio_value = self.config.get("initial_capital", 1_000_000)
        rebalance_dates = self.get_rebalance_dates(freq=rebalance_frequency)
        equity_curve = []
        rebalance_log = []

        print(f"\n🔁 Rebalancing top {top_n} stocks from {start_date.date()} every {rebalance_frequency}")

        for date in rebalance_dates:
            if date < start_date:
                continue

            rankings = self.rank_stocks(as_of_date=date)
            top_symbols = rankings.head(top_n)["Symbol"].tolist()
            print("Top picks:", top_symbols)
            # Step 1: Equal-weight allocation
            weight = 1 / top_n
            allocations = {symbol: weight for symbol in top_symbols}

            # 🔽 LOG the trade here BEFORE moving to next_date
            for symbol, weight in allocations.items():
                price = self.get_price_on_date(symbol, date)
                value = portfolio_value * weight

                rebalance_log.append({
                    "Date": date,
                    "Symbol": symbol,
                    "Weight": round(weight, 4),
                    "Price": round(price, 2) if price else None,
                    "Value": round(value, 2)
                })

            # Step 2: Get next rebalance date
            i = rebalance_dates.index(date)

            if i + 1 >= len(rebalance_dates):
                break  # end of backtest
            next_date = rebalance_dates[i + 1]

            # Step 3: Simulate portfolio return
            period_return = 0
            for symbol, w in allocations.items():
                r = self.get_return_between(symbol, date, next_date)
                period_return += r * w

            # Step 4: Update portfolio value
            portfolio_value *= (1 + period_return)

            # Step 5: Save equity value
            equity_curve.append((next_date, portfolio_value))

            print(f"➡️ {next_date.date()} | Return: {period_return:.2%} | Portfolio: ₹{portfolio_value:,.0f}")
        
        equity_series = pd.Series(dict(equity_curve)).sort_index()
        rebalance_df = pd.DataFrame(rebalance_log)
        benchmark_curve = self.get_benchmark_curve()

        # Initialize the result object
        result = BacktestResult(
            equity_curve=equity_series,
            rebalance_log=rebalance_df,
            benchmark_curve=benchmark_curve  # You can add Nifty 50 later if needed
        )

        # Print Portfolio summary
        portfolio_summary = result.portfolio_summary().iloc[0]  # extract row 0 as Series

        print("\n📊Portfolio Backtest Summary")
        print(f"{'CAGR:':20} {portfolio_summary['CAGR']:.2%}")
        print(f"{'Absolute Return:':20} {portfolio_summary['Absolute Return']:.2%} ({(1 + portfolio_summary['Absolute Return']):.2f}x)")
        print(f"{'Max Drawdown:':20} {portfolio_summary['Max Drawdown']:.2%}")
        print(f"{'Volatility:':20} {portfolio_summary['Volatility']:.2%}")
        print(f"{'Sharpe Ratio:':20} {portfolio_summary['Sharpe Ratio']:.2f}")
        print(f"{'Sortino Ratio:':20} {portfolio_summary['Sortino Ratio']:.2f}")
        print(f"{'Alpha:':20} {portfolio_summary["Alpha"]:.2%}" if portfolio_summary["Alpha"] is not None else f"{'Alpha:':20} N/A")
        print(f"{'Avg Churn/Rebalance:':30} {portfolio_summary['Avg Churn/Rebalance']}")
        print(f"{'Avg Holding Period:':30} {portfolio_summary['Avg Holding Period']} rebalances")

        # Print Benchmark summary
        benchmark_summary = result.benchmark_summary()
        if not benchmark_summary.empty:
            bm = benchmark_summary.iloc[0]
            print("\n📈Benchmark Backtest Summary")
            print(f"{'CAGR:':20} {bm['CAGR']:.2%}")
            print(f"{'Absolute Return:':20} {bm['Absolute Return']}")
            print(f"{'Max Drawdown:':20} {bm['Max Drawdown']:.2%}")
            print(f"{'Volatility:':20} {bm['Volatility']:.2%}")

        # Save CSVs
        strategy_classname = re.sub(r'(?<!^)(?=[A-Z])', '_', self.__class__.__name__).lower()
        result.to_csv(f"reports/{strategy_classname}/")
