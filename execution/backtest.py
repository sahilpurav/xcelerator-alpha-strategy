import os
from datetime import timedelta

import numpy as np
import pandas as pd

from broker.backtest import BacktestBroker
from data.price_fetcher import download_and_cache_prices
from data.universe_fetcher import get_universe_symbols
from logic.planner import plan_allocation
from logic.strategy import run_strategy
from utils.cache import save_to_file
from utils.market import get_last_trading_date


class BacktestEngine:
    """
    Main backtesting engine that runs the Xcelerator Alpha Strategy over historical data.
    """

    def __init__(
        self,
        initial_capital: float = 100_000,
        top_n: int = 15,
        band: int = 5,
        rebalance_frequency: str = "W",
        rebalance_day: str = "Wednesday",
        transaction_cost_pct: float = 0.001192,
        cash_equivalent: str = "LIQUIDCASE.NS",
    ):
        """
        Initialize the backtest engine.

        Args:
            initial_capital: Starting capital in rupees
            top_n: Number of stocks to hold in portfolio
            band: Band for portfolio adjustment (stocks outside top_n + band get sold)
            rebalance_frequency: 'W' for weekly, 'M' for monthly
            rebalance_day: Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday) - only for weekly
            transaction_cost_pct: Transaction cost percentage
            cash_equivalent: Symbol to use as cash equivalent
        """
        self.initial_capital = initial_capital
        self.top_n = top_n
        self.band = band
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_day = rebalance_day.lower()
        self.transaction_cost_pct = transaction_cost_pct
        self.cash_equivalent = cash_equivalent

        # Map day names to weekday numbers (Monday=0, Sunday=6)
        self.day_mapping = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        # Validate rebalance day
        if self.rebalance_day not in self.day_mapping:
            raise ValueError(
                f"Invalid rebalance_day: {rebalance_day}. Must be one of: {list(self.day_mapping.keys())}"
            )

        # Initialize broker
        self.broker = BacktestBroker(initial_capital)

        # Results tracking
        self.portfolio_values = []
        self.rebalance_dates = []
        self.trade_count = 0
        self.total_transaction_cost = 0.0

    def get_universe_and_price_data(
        self, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> tuple[list[str], dict[str, pd.DataFrame]]:
        """
        Get filtered universe and historical price data.
        """
        # Get universe (without ASM/GSM filtering for backtest)
        universe = get_universe_symbols("nifty500")

        # Add .NS suffix for price fetching
        symbols = [f"{s}.NS" for s in universe] + ["^CRSLDX"]

        # Fetch historical data
        start_str = (start_date - timedelta(days=400)).strftime(
            "%Y-%m-%d"
        )  # Extra buffer for indicators
        end_str = end_date.strftime("%Y-%m-%d")

        price_data = download_and_cache_prices(symbols, start=start_str, end=end_str)

        return universe, price_data

    def get_rebalance_dates(
        self, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> list[pd.Timestamp]:
        """
        Generate rebalance dates based on frequency and day preference.
        """
        dates = []

        if self.rebalance_frequency == "W":
            # Generate dates for the entire range
            all_dates = pd.date_range(
                start=start_date,
                end=end_date,
                freq="W-" + self.rebalance_day[:3].upper(),
            )
            dates = [d for d in all_dates if start_date <= d <= end_date]

        elif self.rebalance_frequency == "M":
            current = start_date
            while current <= end_date:
                # Get last day of current month
                if current.month == 12:
                    next_month = current.replace(year=current.year + 1, month=1, day=1)
                else:
                    next_month = current.replace(month=current.month + 1, day=1)

                last_day_of_month = next_month - timedelta(days=1)
                if last_day_of_month <= end_date:
                    dates.append(last_day_of_month)
                current = next_month

        return dates

    def execute_initial_investment(
        self, date: pd.Timestamp, price_data: dict[str, pd.DataFrame]
    ) -> tuple[bool, pd.DataFrame]:
        """
        Execute initial investment on a given date.
        Returns:
            Tuple of (success, execution_df)
        """
        # Run strategy to get recommendations in one call
        recommendations = run_strategy(
            price_data,
            date,
            [],  # No holdings yet
            self.top_n,
            self.band,
            cash_equivalent=self.cash_equivalent,
        )

        # Check if strategy recommends cash equivalent (weak market)
        cash_symbol_clean = self.cash_equivalent.replace(".NS", "")
        is_weak_market = any(
            rec["symbol"] == cash_symbol_clean and rec["action"] in ["BUY", "HOLD"]
            for rec in recommendations
        )

        if is_weak_market:
            # Strategy recommends cash equivalent - treat as weak market
            # In backtest, just hold cash (no actual LIQUIDCASE position)
            return False, pd.DataFrame()  # Return False to indicate weak market regime
            # In weak market, just hold cash - no need to buy LIQUIDCASE
            # The broker already has the cash, no trades needed
            return False, pd.DataFrame()  # Return False to indicate weak market regime

        # For strong market, extract selected symbols from recommendations
        selected_symbols = [
            rec["symbol"] for rec in recommendations if rec["action"] == "BUY"
        ]

        if not selected_symbols:
            return False, pd.DataFrame()

        # Build stock entries from recommendations
        new_stocks = []
        for rec in recommendations:
            if rec["action"] == "BUY":
                symbol_with_ns = f"{rec['symbol']}.NS"
                if (
                    symbol_with_ns in price_data
                    and date in price_data[symbol_with_ns].index
                ):
                    price = price_data[symbol_with_ns].loc[date, "Close"]
                    new_stocks.append(
                        {
                            "symbol": rec["symbol"],
                            "quantity": 0,  # New stock, no existing quantity
                            "last_price": price,
                            "rank": rec["rank"],
                        }
                    )

        # Generate execution plan using plan_allocation
        exec_df, transaction_cost = plan_allocation(
            held_stocks=[],  # No existing holdings
            new_stocks=new_stocks,
            removed_stocks=[],  # No existing holdings to remove
            cash=self.broker.cash,
        )

        # Track transaction cost
        self.total_transaction_cost += transaction_cost

        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)

        return True, exec_df

    def execute_rebalance(
        self, date: pd.Timestamp, price_data: dict[str, pd.DataFrame]
    ) -> tuple[bool, pd.DataFrame]:
        """
        Execute rebalancing on a given date.
        Returns:
            Tuple of (success, execution_df)
        """
        # Get current holdings
        previous_holdings = self.broker.get_holdings()
        held_symbols = [h["symbol"] for h in previous_holdings]

        if not held_symbols:
            return False, pd.DataFrame()

        # Run strategy to get recommendations in one call
        recommendations = run_strategy(
            price_data,
            date,
            held_symbols,
            self.top_n,
            self.band,
            cash_equivalent=self.cash_equivalent,
        )

        # Detect market regime from recommendations
        cash_symbol_clean = self.cash_equivalent.replace(".NS", "")
        is_weak_market = any(
            rec["symbol"] == cash_symbol_clean and rec["action"] in ["BUY", "HOLD"]
            for rec in recommendations
        )

        # If market is weak, move to cash equivalent
        if is_weak_market:
            # In weak market, exit all equity positions and hold cash
            # Don't create actual LIQUIDCASE position - just hold cash in broker

            # Check if we're already in cash (no equity holdings)
            equity_holdings = [
                h for h in previous_holdings if h["symbol"] != cash_symbol_clean
            ]

            if not equity_holdings:
                return False, pd.DataFrame()  # Already in cash, no action needed

            # Plan to sell all equity positions
            removed_stocks = []
            for holding in equity_holdings:
                symbol = holding["symbol"]
                symbol_with_ns = f"{symbol}.NS"
                if (
                    symbol_with_ns in price_data
                    and date in price_data[symbol_with_ns].index
                ):
                    price = price_data[symbol_with_ns].loc[date, "Close"]
                    removed_stocks.append(
                        {
                            "symbol": symbol,
                            "quantity": holding["quantity"],
                            "last_price": price,
                            "rank": None,
                        }
                    )

            # Create execution plan to sell all equities (no new purchases)
            exec_df = pd.DataFrame()
            transaction_cost = 0.0
            if removed_stocks:
                # Manually create execution plan for sells and calculate transaction costs
                sells_data = []
                for stock in removed_stocks:
                    sell_value = stock["quantity"] * stock["last_price"]
                    # Calculate transaction cost for this sell (same rate as plan_allocation uses)
                    transaction_cost += sell_value * self.transaction_cost_pct
                    
                    sells_data.append(
                        {
                            "Symbol": stock["symbol"],
                            "Rank": "N/A",
                            "Action": "SELL",
                            "Price": round(stock["last_price"], 2),
                            "Quantity": int(stock["quantity"]),
                            "Invested": round(sell_value, 2),
                        }
                    )
                exec_df = pd.DataFrame(sells_data)

            # Track transaction cost
            self.total_transaction_cost += transaction_cost

            # Execute sell trades
            if not exec_df.empty:
                self._execute_backtest_orders(exec_df, date, price_data)
            return False, exec_df  # Return False to indicate weak market

        # For strong market, categorize recommendations
        held_stocks = []
        new_stocks = []
        removed_stocks = []

        for rec in recommendations:
            symbol = rec["symbol"]
            action = rec["action"]
            rank = rec["rank"]

            # Skip cash equivalent in strong market recommendations
            if symbol == cash_symbol_clean:
                continue

            # Get price data for regular equities
            symbol_with_ns = f"{symbol}.NS"
            if (
                symbol_with_ns not in price_data
                or date not in price_data[symbol_with_ns].index
            ):
                continue
            price = price_data[symbol_with_ns].loc[date, "Close"]

            # Get existing quantity from holdings
            existing_holding = next(
                (h for h in previous_holdings if h["symbol"] == symbol), None
            )
            quantity = existing_holding["quantity"] if existing_holding else 0

            stock_entry = {
                "symbol": symbol,
                "quantity": quantity if action in ["HOLD", "SELL"] else 0,
                "last_price": price,
                "rank": rank,
            }

            if action == "BUY":
                new_stocks.append(stock_entry)
            elif action == "HOLD":
                held_stocks.append(stock_entry)
            elif action == "SELL":
                removed_stocks.append(stock_entry)

        # Check if any changes are needed
        if not new_stocks and not removed_stocks:
            return True, pd.DataFrame()  # No changes needed

        # Generate execution plan
        exec_df, transaction_cost = plan_allocation(
            held_stocks=held_stocks,
            new_stocks=new_stocks,
            removed_stocks=removed_stocks,
            cash=self.broker.cash,
        )

        # Track transaction cost
        self.total_transaction_cost += transaction_cost

        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)

        return True, exec_df

    def _execute_backtest_orders(
        self,
        exec_df: pd.DataFrame,
        date: pd.Timestamp,
        price_data: dict[str, pd.DataFrame],
    ):
        """
        Execute orders from execution plan using backtest broker.
        """
        if exec_df.empty:
            return

        # Execute SELLs first, then BUYs (same as live system)
        for action in ["SELL", "BUY"]:
            action_df = exec_df[exec_df["Action"] == action]

            for _, row in action_df.iterrows():
                symbol = str(row["Symbol"])
                quantity = int(row["Quantity"])
                price = float(row["Price"])

                if quantity > 0:
                    order_id = self.broker.place_order(
                        symbol=symbol,
                        quantity=quantity,
                        transaction_type=action,
                        price=price,
                        date=date,
                    )

                    if order_id:
                        self.trade_count += 1

    def track_portfolio_value(
        self, date: pd.Timestamp, price_data: dict[str, pd.DataFrame]
    ):
        """
        Track daily portfolio value for performance analysis.
        """
        portfolio_value = self.broker.get_portfolio_value(price_data, date)
        self.portfolio_values.append((date, portfolio_value))

    def run_backtest(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> dict:
        """
        Run the complete backtest.

        Returns:
            Dictionary with backtest results and performance metrics
        """
        # Get data
        universe, price_data = self.get_universe_and_price_data(start_date, end_date)

        # Get rebalance dates
        rebalance_dates = self.get_rebalance_dates(start_date, end_date)

        # Track if we've made initial investment
        initial_invested = False
        last_portfolio_value = self.initial_capital

        # Get all trading dates for daily portfolio tracking
        if "^CRSLDX" in price_data:
            all_dates = price_data["^CRSLDX"].index
            trading_dates = [d for d in all_dates if start_date <= d <= end_date]
        else:
            trading_dates = rebalance_dates

        # Main backtest loop
        for date in trading_dates:
            # Track daily portfolio value
            self.track_portfolio_value(date, price_data)

            # Apply liquid fund returns for current date

            current_value = self.broker.get_portfolio_value(price_data, date)
            pct_change = (
                ((current_value - last_portfolio_value) / last_portfolio_value * 100)
                if last_portfolio_value > 0
                else 0
            )

            # Check if this is a rebalance date
            if date in rebalance_dates:
                self.rebalance_dates.append(date)

                is_weak_market = False

                # Execute trades first to determine market regime
                if not initial_invested:
                    success, exec_df = self.execute_initial_investment(date, price_data)
                    initial_invested = success
                    is_weak_market = not success
                else:
                    success, exec_df = self.execute_rebalance(date, price_data)
                    is_weak_market = not success

                # Print header
                print("\n" + "=" * 80)
                if not initial_invested:
                    print(
                        f"📅 INITIAL INVESTMENT ── {date.strftime('%Y-%m-%d')}   {'⚠️  WEAK MARKET' if is_weak_market else '💪 STRONG MARKET'}"
                    )
                else:
                    print(
                        f"📅 REBALANCE SUMMARY ── {date.strftime('%Y-%m-%d')}   {'⚠️  WEAK MARKET' if is_weak_market else '💪 STRONG MARKET'}"
                    )
                print("=" * 80 + "\n")

                # Print portfolio snapshot
                print("📈 PORTFOLIO SNAPSHOT")
                print("─" * 80)
                print(f"  DATE           : {date.strftime('%Y-%m-%d')}")
                print(f"  VALUE          : ₹{current_value:,.2f}")

                change_symbol = (
                    "▲" if pct_change > 0 else "▼" if pct_change < 0 else "▬"
                )
                print(
                    f"  CHANGE         : {change_symbol} {'+' if pct_change >= 0 else ''}{pct_change:.2f}%"
                )
                print("─" * 80 + "\n")

                if is_weak_market:
                    print("⚠️  All equity positions exited due to weak market regime.")
                    print("─" * 80)
                elif not exec_df.empty:
                    print("🔄 TRADE ACTIONS")
                    print("─" * 80)

                    sells = exec_df[exec_df["Action"] == "SELL"]
                    buys = exec_df[exec_df["Action"] == "BUY"]

                    if not sells.empty:
                        sold_symbols = sells["Symbol"].tolist()
                        print(f"  SOLD           : {wrap_symbols(sold_symbols)}\n")

                    if not buys.empty:
                        bought_symbols = buys["Symbol"].tolist()
                        print(f"  BOUGHT         : {wrap_symbols(bought_symbols)}")

                    print("─" * 80)

                # Show current portfolio after rebalance
                current_holdings = self.broker.get_holdings()
                if current_holdings:
                    print("\n📊 STOCK PORTFOLIO")
                    print("─" * 80)
                    portfolio_symbols = [
                        holding["symbol"] for holding in current_holdings
                    ]
                    print(
                        f"  HOLDINGS ({len(portfolio_symbols)})  : {wrap_symbols(portfolio_symbols)}"
                    )
                    print("─" * 80)

                last_portfolio_value = current_value

                # Check if we've exited all positions due to weak market regime
                current_holdings = self.broker.get_holdings()
                if not current_holdings:
                    initial_invested = False

        # Generate and print results
        results = self._generate_results()
        self._print_summary(results)

        return results

    def _generate_results(self) -> dict:
        """
        Generate performance metrics and results.
        """
        if not self.portfolio_values:
            return {}

        # Convert to DataFrame
        df_values = pd.DataFrame(
            self.portfolio_values, columns=["date", "portfolio_value"]
        )
        df_values.set_index("date", inplace=True)

        # Calculate returns
        df_values["daily_return"] = df_values["portfolio_value"].pct_change()
        df_values["cumulative_return"] = (
            df_values["portfolio_value"] / self.initial_capital - 1
        )

        # Performance metrics
        total_return = (
            df_values["portfolio_value"].iloc[-1] / self.initial_capital - 1
        ) * 100

        # Annualized return (approximate)
        days = (df_values.index[-1] - df_values.index[0]).days
        years = days / 365.25
        cagr = (
            (
                (df_values["portfolio_value"].iloc[-1] / self.initial_capital)
                ** (1 / years)
                - 1
            )
            * 100
            if years > 0
            else 0
        )

        # Max drawdown
        running_max = df_values["portfolio_value"].expanding().max()
        drawdown = (df_values["portfolio_value"] - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        # Volatility (annualized)
        daily_returns = df_values["daily_return"].dropna()
        volatility = daily_returns.std() * np.sqrt(252) * 100

        # Sharpe ratio (assuming 6% risk-free rate)
        risk_free_rate = 0.06
        excess_return = cagr - risk_free_rate * 100
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0

        # Adjusted metrics (accounting for transaction costs)
        adjusted_final_value = df_values["portfolio_value"].iloc[-1] - self.total_transaction_cost
        adjusted_total_return = (
            (adjusted_final_value / self.initial_capital - 1) * 100
        )
        adjusted_cagr = (
            (
                (adjusted_final_value / self.initial_capital) ** (1 / years)
                - 1
            )
            * 100
            if years > 0
            else 0
        )

        return {
            "start_date": df_values.index[0],
            "end_date": df_values.index[-1],
            "initial_capital": self.initial_capital,
            "final_value": df_values["portfolio_value"].iloc[-1],
            "total_return_pct": total_return,
            "cagr_pct": cagr,
            "adjusted_final_value": adjusted_final_value,  # New
            "adjusted_total_return_pct": adjusted_total_return,  # New
            "adjusted_cagr_pct": adjusted_cagr,  # New
            "max_drawdown_pct": max_drawdown,
            "volatility_pct": volatility,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": self.trade_count,
            "rebalance_count": len(self.rebalance_dates),
            "total_transaction_cost": self.total_transaction_cost,
            "portfolio_values": df_values,
            "transactions": self.broker.get_transactions(),
        }

    def _print_summary(self, results: dict):
        """
        Print backtest summary.
        """
        print("\n" + "=" * 60)
        print("📈 BACKTEST RESULTS SUMMARY")
        print("=" * 60)
        print(
            f"🗓️  Period: {results['start_date'].date()} to {results['end_date'].date()}"
        )
        print(f"💰 Initial Capital: ₹{results['initial_capital']:,.2f}")
        print(f"💎 Final Value: ₹{results['final_value']:,.2f}")
        print(f"📊 Total Return: {results['total_return_pct']:.2f}%")
        print(f"📈 CAGR: {results['cagr_pct']:.2f}%")
        print(f"📉 Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"📊 Volatility: {results['volatility_pct']:.2f}%")
        print(f"⚡ Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"🔄 Total Trades: {results['total_trades']}")
        print(f"📅 Rebalances: {results['rebalance_count']}")
        print(f"💸 Transaction Costs: ₹{results['total_transaction_cost']:,.2f}")
        print(
            f"💎 Final Value (Adj.): ₹{results['adjusted_final_value']:,.2f}"  # New
        )
        print(
            f"📊 Total Return (Adj.): {results['adjusted_total_return_pct']:.2f}%"  # New
        )
        print(
            f"📈 CAGR (Adj.): {results['adjusted_cagr_pct']:.2f}%"  # New
        )
        print("=" * 60)


def wrap_symbols(symbols: list[str], width: int = 65) -> str:
    """Wrap a list of symbols to fit within specified width."""
    lines = []
    current_line = []
    current_width = 0

    for symbol in symbols:
        # Account for ", " that will be added between symbols
        symbol_width = len(symbol) + 2

        if current_width + symbol_width > width:
            lines.append(", ".join(current_line))
            current_line = [symbol]
            current_width = symbol_width
        else:
            current_line.append(symbol)
            current_width += symbol_width

    if current_line:
        lines.append(", ".join(current_line))

    return "\n               ".join(lines)  # Align with the label spacing


def run_backtest(
    start: str,
    end: str | None = None,
    rebalance_day: str = "Wednesday",
    band: int = 5,
    top_n: int = 15,
    cash_equivalent: str = "LIQUIDCASE.NS",
):
    """
    Main entry point for backtesting from CLI.
    This function will be executed when you run `python cli.py backtest`

    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format (optional, defaults to last trading day)
        rebalance_day: Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)
        band: Band size for portfolio stability (higher = less churn)
        cash_equivalent: Symbol to use as cash equivalent (for detecting weak market)
    """
    start_date = pd.to_datetime(start)
    end_date = pd.to_datetime(end) if end else pd.to_datetime(get_last_trading_date())

    # Initialize and run backtest
    engine = BacktestEngine(
        initial_capital=10_00_000,  # Default 10 lakh
        top_n=top_n,
        band=band,
        rebalance_frequency="W",
        rebalance_day=rebalance_day,
        cash_equivalent=cash_equivalent,
    )

    results = engine.run_backtest(start_date, end_date)

    # Save results to output folder
    if results:

        # Save portfolio values
        portfolio_file = (
            f"output/backtest-portfolio-{start}-{end_date.strftime('%Y-%m-%d')}.csv"
        )
        # Reset index to include date as a column and reorder columns
        portfolio_df_with_date = results["portfolio_values"].reset_index()
        portfolio_df_with_date = portfolio_df_with_date[["date", "portfolio_value", "daily_return", "cumulative_return"]]
        portfolio_records = portfolio_df_with_date.to_dict("records")
        if save_to_file(portfolio_records, portfolio_file):
            print(f"📁 Portfolio values saved to: {portfolio_file}")
        else:
            print("⚠️ Caching is disabled - portfolio values were not saved")

        # Save transactions
        transactions_df = results["transactions"]
        if not transactions_df.empty:
            transactions_file = f"output/backtest-transactions-{start}-{end_date.strftime('%Y-%m-%d')}.csv"
            transaction_records = transactions_df.to_dict("records")
            if save_to_file(transaction_records, transactions_file):
                print(f"💾 Transactions saved to: {transactions_file}")
            else:
                print("⚠️ Caching is disabled - transactions were not saved")

    return results
