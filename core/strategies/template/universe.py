from core.universe import Universe
from core.stock import Stock
from typing import Dict
import pandas as pd
from core.reporting.backtest_result import BacktestResult
from core.reporting.equity_curve import EquityCurveSimulator
import re
from utils.indicators import Indicator
import math
import datetime

class UniverseStrategy:
    def __init__(self, config: Dict):
        self.config = config
        self.universe_name = config.get("universe", "nifty500")
        self.start_date = config.get("start_date", "2015-01-01")
        self.force_refresh = config.get("force_refresh", False)
        self.backtest_results = {}

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
        
        days_ago = 200
        df_subset = df[df.index <= as_of_date]
        if df_subset.shape[0] < days_ago:
            return True  # Not enough data

        ind = Indicator(df_subset)
        dma = ind.dma(days_ago)
        latest_close = df_subset["Close"].iloc[-1]

        if dma is None:
            return True

        return latest_close > dma
    
    def get_rebalance_dates(self, freq: str = "W") -> list[pd.Timestamp]:
        """
        Generate rebalance dates aligned to available trading days.
        """
        first_symbol = next(iter(self.price_data))
        all_dates = self.price_data[first_symbol].index.to_series()
        rebalance_dates = all_dates.resample(freq).first().dropna().index.tolist()
        return rebalance_dates
    
    def get_price_on_date(self, symbol: str, date: pd.Timestamp) -> tuple[float, pd.Timestamp]:
        """
        Returns (price, actual_date_used).
        Falls back to nearest previous available date if date not in index.
        """
        df = self.price_data.get(symbol)
        if df is None or df.empty:
            return None, None

        if date in df.index:
            return df.loc[date]["Close"], date

        df = df[df.index < date]
        if df.empty:
            return None, None

        actual_date = df.index[-1]
        return df.loc[actual_date]["Close"], actual_date

    
    def get_return_between(self, symbol: str, from_date: pd.Timestamp, to_date: pd.Timestamp) -> float:
        """
        Calculates the % return for a symbol between two dates using Close prices.
        """
        price_start, _ = self.get_price_on_date(symbol, from_date)
        price_end, _ = self.get_price_on_date(symbol, to_date)

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

    def run(self, top_n: int = 15, band_threshold: int = 5, previous_holdings: list[dict] = []):
        """
        Rebalance using banding logic. Preserve existing holdings, reinvest only proceeds from removed stocks.

        Args:
            top_n (int): Number of stocks to hold
            band_threshold (int): Ranking flexibility band
            previous_holdings (list): List of dicts: [{"symbol": "XYZ", "quantity": 100, "buy_price": 150.0}, ...]

        Returns:
            list[str]: Final portfolio symbols
        """
        prev_symbols = [d["symbol"] for d in previous_holdings]
        latest_date = pd.Timestamp(datetime.datetime.now().date())
        rankings = self.rank_stocks(as_of_date=latest_date)

        if rankings.empty:
            print("⚠️ No valid ranking for today. Likely due to weak market filter.")
            return []

        rankings = rankings.reset_index(drop=True)
        rankings["Rank"] = rankings.index + 1
        rankings["CleanSymbol"] = rankings["Symbol"].str.replace(".NS", "", regex=False)

        held_stocks = []
        held_details = []
        removed_details = []

        if band_threshold > 0:
            for symbol in prev_symbols:
                if symbol in rankings["CleanSymbol"].values:
                    rank = rankings.loc[rankings["CleanSymbol"] == symbol, "Rank"].values[0]
                    if rank <= top_n + band_threshold:
                        held_stocks.append(symbol)
                        held_details.append({"Symbol": symbol, "Rank": rank})
                    else:
                        removed_details.append({"Symbol": symbol, "Rank": rank})
                else:
                    removed_details.append({"Symbol": symbol, "Rank": "N/A"})

        slots_remaining = top_n - len(held_stocks)
        new_candidates = rankings[~rankings["CleanSymbol"].isin(held_stocks)]
        new_rows = new_candidates.head(slots_remaining)[["CleanSymbol", "Rank"]]
        new_symbols = new_rows["CleanSymbol"].tolist()
        new_details = new_rows.rename(columns={"CleanSymbol": "Symbol"}).to_dict(orient="records")

        final_portfolio = held_stocks + new_symbols

        print(f"\n📅 Live Rebalance Date: {latest_date.date()}")
        print(f"✅ Final Portfolio (Band = {band_threshold})\n")

        if held_details:
            df_held = pd.DataFrame(held_details).sort_values("Rank")
            print("🟢 Held Stocks (within band)")
            print(df_held.to_string(index=False))

        if new_details:
            df_new = pd.DataFrame(new_details).sort_values("Rank")
            print("\n🆕 New Entries")
            print(df_new.to_string(index=False))

        if removed_details:
            df_removed = pd.DataFrame(removed_details)
            df_removed["Rank"] = pd.to_numeric(df_removed["Rank"], errors="coerce")
            df_removed = df_removed.sort_values("Rank", na_position="last")
            df_removed["Rank"] = df_removed["Rank"].fillna("N/A")
            print("\n❌ Removed Stocks (outside band)")
            print(df_removed.to_string(index=False))

        # --- Execution Plan ---

        # Get latest close prices
        latest_close = {
            symbol.replace(".NS", ""): df.loc[latest_date, "Close"]
            for symbol, df in self.price_data.items()
            if latest_date in df.index
        }

        # Convert to DataFrame
        prev_df = pd.DataFrame(previous_holdings)
        prev_df["current_price"] = prev_df["symbol"].map(latest_close)
        prev_df["effective_price"] = prev_df.apply(
            lambda row: row["buy_price"] if pd.notna(row.get("buy_price")) and row["buy_price"] > 0 else row["current_price"],
            axis=1
        )
        prev_df["current_value"] = prev_df["quantity"] * prev_df["effective_price"]

        # Split into held and removed
        df_held = prev_df[prev_df["symbol"].isin(held_stocks)].copy()
        df_removed = prev_df[prev_df["symbol"].isin([d["Symbol"] for d in removed_details])].copy()

        # Total capital freed from sells
        freed_capital = df_removed["current_value"].sum()

        # Total portfolio value = held + freed capital
        total_portfolio_value = df_held["current_value"].sum() + freed_capital

        # Allocate equally to new entries
        per_stock_alloc = freed_capital / len(new_symbols) if new_symbols else 0

        # Create rank lookups
        held_rank_map = {d["Symbol"]: d["Rank"] for d in held_details}
        new_rank_map = {d["Symbol"]: d["Rank"] for d in new_details}

        execution_data = []

        # --- Add held stocks with original quantity ---
        for _, row in df_held.iterrows():
            symbol = row["symbol"]
            invested = round(row["quantity"] * row["current_price"], 2)
            execution_data.append({
                "Symbol": row["symbol"],
                "Rank": held_rank_map.get(symbol, "N/A"),
                "Price": round(row["current_price"], 2),
                "Quantity": int(row["quantity"]),
                "Invested": invested,
                "Weight %": round((invested / total_portfolio_value) * 100, 2),
                "Action": "HOLD"
            })

        # --- Add new stocks with equal weight from freed capital ---
        for symbol in new_symbols:
            price = latest_close.get(symbol)
            if not price or price == 0:
                continue
            qty = math.floor(per_stock_alloc / price)
            invested = round(qty * price, 2)
            execution_data.append({
                "Symbol": symbol,
                "Rank": new_rank_map.get(symbol, "N/A"),
                "Price": round(price, 2),
                "Quantity": qty,
                "Invested": invested,
                "Weight %": round((invested / total_portfolio_value) * 100, 2),
                "Action": "BUY"
            })

        df_exec = pd.DataFrame(execution_data).sort_values("Rank")

        print("\n📦 Final Execution Plan")
        print(df_exec.to_string(index=False))

        return final_portfolio


    
    def backtest(self, top_n: int = 20, rebalance_frequency: str = "W", band_threshold: int = 0):
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
                actual_dates = []
                for symbol, (qty, _) in current_holdings.items():
                    price, actual_date = self.get_price_on_date(symbol, date)
                    if price:
                        equity_value += qty * price
                        actual_dates.append(actual_date)

                # Use the latest price date among holdings as the rebalance action date
                rebalance_date_used = max(actual_dates) if actual_dates else date
                portfolio_value = equity_value + cash

                rebalance_log.append({
                    "Date": rebalance_date_used,
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

            held_stocks = []
            if band_threshold > 0:
                max_rank = top_n + band_threshold
                rankings = rankings.reset_index(drop=True)
                rankings["Rank"] = rankings.index + 1

                # Step 1: Keep currently held stocks if they are within the band
                for symbol in list(current_holdings.keys()):
                    if symbol in rankings["Symbol"].values:
                        current_rank = rankings.loc[rankings["Symbol"] == symbol, "Rank"].values[0]
                        if current_rank <= max_rank:
                            held_stocks.append(symbol)

                # Step 2: Fill remaining slots with top ranked symbols not already held
                slots_left = top_n - len(held_stocks)
                new_symbols = rankings[~rankings["Symbol"].isin(held_stocks)] \
                                    .sort_values("TotalRank") \
                                    .head(slots_left)["Symbol"].tolist()

                top_symbols = held_stocks + new_symbols
            else:
                top_symbols = rankings.head(top_n)["Symbol"].tolist()
            print("Top picks:", top_symbols)

            # Sell stocks that are no longer in top N
            new_cash = cash
            for symbol in list(current_holdings.keys()):
                if symbol not in top_symbols:
                    qty, buy_price = current_holdings[symbol]
                    sell_price, sell_price_date = self.get_price_on_date(symbol, date)
                    if sell_price:
                        proceeds = qty * sell_price
                        new_cash += proceeds
                        rebalance_log.append({
                            "Date": sell_price_date,
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

                price, buy_price_date = self.get_price_on_date(symbol, date)
                if price is None or price == 0:
                    continue

                qty = int(capital_per_stock // price)
                cost = qty * price
                if qty > 0:
                    current_holdings[symbol] = (qty, price)
                    new_cash -= cost
                    rebalance_log.append({
                        "Date": buy_price_date,
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
            actual_dates = []
            for symbol, (qty, _) in current_holdings.items():
                price, actual_date = self.get_price_on_date(symbol, next_date)
                if price:
                    equity_value += qty * price
                    actual_dates.append(actual_date)

            portfolio_value = equity_value + cash
            rebalance_value_date = max(actual_dates) if actual_dates else next_date
            equity_curve.append((rebalance_value_date, portfolio_value))

            prev_value = equity_curve[-2][1] if len(equity_curve) > 1 else initial_capital
            return_pct = (portfolio_value / prev_value) - 1 if prev_value else 0
            print(f"\u27a1\ufe0f {next_date.date()} | Weekly Return: {return_pct:.2%} | Portfolio: ₹{portfolio_value:,.0f}")

        # Finalize results
        equity_series = pd.Series(dict(equity_curve)).sort_index()
        rebalance_df = pd.DataFrame(rebalance_log)
        benchmark_curve = self.get_benchmark_curve()

        benchmark_symbol = self.config.get("benchmark", "^NSEI")
        nsei_data = self.price_data.get(benchmark_symbol)

        daily_equity_series = EquityCurveSimulator.simulate(
            rebalance_log=rebalance_df,
            price_data=self.price_data,
            nsei_data=nsei_data,
            initial_capital=initial_capital
        )

        result = BacktestResult(
            equity_curve=equity_series,
            rebalance_log=rebalance_df,
            benchmark_curve=benchmark_curve,
            daily_equity_curve=daily_equity_series
        )

        portfolio_summary = result.portfolio_summary().iloc[0]
        # Create a structured dictionary with all performance metrics
        strategy_classname = re.sub(r'(?<!^)(?=[A-Z])', '_', self.__class__.__name__).lower()
        
        self.backtest_results = {
            "strategy_name": strategy_classname,
            "portfolio": {
                "cagr": portfolio_summary['CAGR'],
                "absolute_return": portfolio_summary['Absolute Return'],
                "absolute_return_multiple": (1 + portfolio_summary['Absolute Return']),
                "max_drawdown": portfolio_summary['Max Drawdown'],
                "volatility": portfolio_summary['Volatility'],
                "sharpe_ratio": portfolio_summary['Sharpe Ratio'],
                "sortino_ratio": portfolio_summary['Sortino Ratio'],
                "alpha": portfolio_summary['Alpha'],
                "avg_churn_per_rebalance": portfolio_summary['Avg Churn/Rebalance'],
                "avg_holding_period": portfolio_summary['Avg Holding Period'],
                "daily_max_drawdown": portfolio_summary['Daily Max Drawdown'],
                "daily_max_gain": portfolio_summary['Daily Max Gain'],
                "avg_daily_gain": portfolio_summary['Avg Daily Gain'],
                "avg_daily_loss": portfolio_summary['Avg Daily Loss'],
                "win_rate": portfolio_summary['Win Rate'],
                "loss_rate": portfolio_summary['Loss Rate'],
                "daily_return_std_dev": portfolio_summary['Daily Return Std Dev'],
                "max_win_streak": portfolio_summary['Max Win Streak'],
                "max_loss_streak": portfolio_summary['Max Loss Streak']
            },
            "benchmark": {}
        }
        
        # Add benchmark data if available
        benchmark_summary = result.benchmark_summary()
        if not benchmark_summary.empty:
            bm = benchmark_summary.iloc[0]
            self.backtest_results["benchmark"] = {
                "cagr": bm['CAGR'],
                "absolute_return": bm['Absolute Return'],
                "max_drawdown": bm['Max Drawdown'],
                "volatility": bm['Volatility']
            }

        # Save results to CSV
        result.to_csv(f"reports/{strategy_classname}/")
        
        return self
    
    def summary(self):
        def fmt_pct(val):
            return f"{val:.2%}" if isinstance(val, (int, float)) else str(val)
    
        def fmt_float(val):
            return f"{val:.2f}" if isinstance(val, (int, float)) else str(val)

        # Access the results dictionary directly (single strategy case)
        portfolio_summary = self.backtest_results.get('portfolio', {})
        benchmark_summary = self.backtest_results.get('benchmark', {})
        pretty_name = " ".join(word.capitalize() for word in self.backtest_results.get('strategy_name', '').split("_")) + " Strategy"
        print(f"\n\U0001f4caPortfolio Backtest Summary ({pretty_name})")

        print(f"{'CAGR:':20} {fmt_pct(portfolio_summary.get('cagr', 'N/A'))}")
        print(f"{'Absolute Return:':20} {fmt_pct(portfolio_summary.get('absolute_return', 'N/A'))} ({fmt_float(portfolio_summary.get('absolute_return_multiple', 'N/A'))}x)")
        print(f"{'Max Drawdown:':20} {fmt_pct(portfolio_summary.get('max_drawdown', 'N/A'))}")
        print(f"{'Volatility:':20} {fmt_pct(portfolio_summary.get('volatility', 'N/A'))}")
        print(f"{'Sharpe Ratio:':20} {fmt_float(portfolio_summary.get('sharpe_ratio', 'N/A'))}")
        print(f"{'Sortino Ratio:':20} {fmt_float(portfolio_summary.get('sortino_ratio', 'N/A'))}")
        alpha = portfolio_summary.get('alpha', 'N/A')
        if isinstance(alpha, (int, float)):
            print(f"{'Alpha:':20} {fmt_pct(alpha)}")
        else:
            print(f"{'Alpha:':20} {alpha}")
        print(f"{'Avg Churn/Rebalance:':30} {portfolio_summary.get('avg_churn_per_rebalance', 'N/A')}")
        print(f"{'Avg Holding Period:':30} {portfolio_summary.get('avg_holding_period', 'N/A')} rebalances")
        print(f"{'Daily Max Drawdown:':30} {fmt_pct(portfolio_summary.get('daily_max_drawdown', 'N/A'))}")
        print(f"{'Daily Max Gain:':30} {fmt_pct(portfolio_summary.get('daily_max_gain', 'N/A'))}")
        print(f"{'Avg Daily Gain:':30} {fmt_pct(portfolio_summary.get('avg_daily_gain', 'N/A'))}")
        print(f"{'Avg Daily Loss:':30} {fmt_pct(portfolio_summary.get('avg_daily_loss', 'N/A'))}")
        print(f"{'Win Rate:':30} {fmt_pct(portfolio_summary.get('win_rate', 'N/A'))}")
        print(f"{'Loss Rate:':30} {fmt_pct(portfolio_summary.get('loss_rate', 'N/A'))}")
        print(f"{'Daily Return Std Dev:':30} {fmt_pct(portfolio_summary.get('daily_return_std_dev', 'N/A'))}")
        print(f"{'Max Win Streak:':30} {portfolio_summary.get('max_win_streak', 'N/A')} days")
        print(f"{'Max Loss Streak:':30} {portfolio_summary.get('max_loss_streak', 'N/A')} days")

        # Print benchmark summary only once at the end
        if benchmark_summary:
            print(f"\n\U0001f4c8Benchmark Backtest Summary")
            print(f"{'CAGR:':20} {fmt_pct(benchmark_summary.get('cagr', 'N/A'))}")
            print(f"{'Absolute Return:':20} {fmt_pct(benchmark_summary.get('absolute_return', 'N/A'))}")
            print(f"{'Max Drawdown:':20} {fmt_pct(benchmark_summary.get('max_drawdown', 'N/A'))}")
            print(f"{'Volatility:':20} {fmt_pct(benchmark_summary.get('volatility', 'N/A'))}")
