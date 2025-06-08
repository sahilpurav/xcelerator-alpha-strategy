import pandas as pd
import numpy as np
import os
from datetime import timedelta
from typing import Dict, List, Tuple
from broker.backtest import BacktestBroker
from data.universe_fetcher import get_universe_symbols
from data.price_fetcher import download_and_cache_prices
from logic.strategy import get_ranked_stocks, generate_band_adjusted_portfolio
from logic.planner import plan_initial_investment, plan_rebalance_investment, plan_exit_all_positions
from utils.date import get_last_trading_day

class BacktestEngine:
    """
    Main backtesting engine that runs the Xcelerator Alpha Strategy over historical data.
    """
    
    def __init__(self, initial_capital: float = 100_000, top_n: int = 15, band: int = 5, 
                 rebalance_frequency: str = "W", rebalance_day: str = "Wednesday", transaction_cost_pct: float = 0.001190):
        """
        Initialize the backtest engine.
        
        Args:
            initial_capital: Starting capital in rupees
            top_n: Number of stocks to hold in portfolio
            band: Band for portfolio adjustment (stocks outside top_n + band get sold)
            rebalance_frequency: 'W' for weekly, 'M' for monthly
            rebalance_day: Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday) - only for weekly
            transaction_cost_pct: Transaction cost percentage
        """
        self.initial_capital = initial_capital
        self.top_n = top_n
        self.band = band
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_day = rebalance_day.lower()
        self.transaction_cost_pct = transaction_cost_pct
        
        # Map day names to weekday numbers (Monday=0, Sunday=6)
        self.day_mapping = {
            "monday": 0, "tuesday": 1, "wednesday": 2, 
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
        }
        
        # Validate rebalance day
        if self.rebalance_day not in self.day_mapping:
            raise ValueError(f"Invalid rebalance_day: {rebalance_day}. Must be one of: {list(self.day_mapping.keys())}")
        
        # Initialize broker
        self.broker = BacktestBroker(initial_capital, transaction_cost_pct)
        
        # Track performance
        self.portfolio_values = []  # [(date, portfolio_value)]
        self.rebalance_dates = []
        self.trade_count = 0
        
    def get_universe_and_price_data(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Tuple[List[str], Dict[str, pd.DataFrame]]:
        """
        Get filtered universe and historical price data.
        """
        # Get universe (without ASM/GSM filtering for backtest)
        universe = get_universe_symbols("nifty500")
        
        # Add .NS suffix for price fetching
        symbols = [f"{s}.NS" for s in universe] + ["^CRSLDX"]
        
        # Fetch historical data
        start_str = (start_date - timedelta(days=400)).strftime("%Y-%m-%d")  # Extra buffer for indicators
        end_str = end_date.strftime("%Y-%m-%d")
        
        price_data = download_and_cache_prices(symbols, start=start_str, end=end_str)
        
        return universe, price_data
    
    def get_rebalance_dates(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> List[pd.Timestamp]:
        """
        Generate rebalance dates based on frequency and day preference.
        """
        dates = []
        
        if self.rebalance_frequency == "W":
            # Generate dates for the entire range
            all_dates = pd.date_range(start=start_date, end=end_date, freq='W-' + self.rebalance_day[:3].upper())
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
    
    def execute_initial_investment(self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]) -> Tuple[bool, pd.DataFrame]:
        """
        Execute initial investment on the first rebalance date.
        
        Returns:
            Tuple of (success, execution_df)
        """
        # Get ranked stocks
        ranked_df = get_ranked_stocks(price_data, date)
        
        if ranked_df.empty:
            return False, pd.DataFrame()
        
        # Select top N stocks
        top_n_df = ranked_df.nsmallest(self.top_n, "total_rank")
        selected_symbols = top_n_df["symbol"].tolist()
        
        # Generate execution plan
        exec_df = plan_initial_investment(
            symbols=selected_symbols,
            price_data=price_data,
            as_of_date=date,
            total_capital=self.broker.cash,
            ranked_df=ranked_df
        )
        
        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)
        
        return True, exec_df
    
    def execute_rebalance(self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]) -> Tuple[bool, pd.DataFrame]:
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
        
        # Get ranked stocks
        ranked_df = get_ranked_stocks(price_data, date)
        
        if ranked_df.empty:
            # Plan complete exit
            exec_df = plan_exit_all_positions(
                previous_holdings=previous_holdings,
                price_data=price_data,
                as_of_date=date,
                ranked_df=pd.DataFrame()  # Empty DataFrame for weak regime
            )
            
            # Execute exit trades
            if not exec_df.empty:
                self._execute_backtest_orders(exec_df, date, price_data)
            return False, exec_df
        
        # Determine portfolio changes using band logic
        held, new_entries, removed, _ = generate_band_adjusted_portfolio(
            ranked_df,
            held_symbols,
            self.top_n,
            self.band
        )
        
        if not new_entries and not removed:
            return True, pd.DataFrame()
        
        # Generate execution plan
        exec_df = plan_rebalance_investment(
            held_stocks=held,
            new_entries=new_entries,
            removed_stocks=removed,
            previous_holdings=previous_holdings,
            price_data=price_data,
            as_of_date=date,
            ranked_df=ranked_df,
            transaction_cost_pct=self.transaction_cost_pct
        )
        
        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)
        
        return True, exec_df
    
    def _execute_backtest_orders(self, exec_df: pd.DataFrame, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]):
        """
        Execute orders from execution plan using backtest broker.
        """
        if exec_df.empty:
            return
        
        # Execute SELLs first, then BUYs (same as live system)
        for action in ["SELL", "BUY"]:
            action_df = exec_df[exec_df["Action"] == action]
            
            for _, row in action_df.iterrows():
                symbol = row["Symbol"]
                quantity = int(row["Quantity"])
                price = float(row["Price"])
                
                if quantity > 0:
                    order_id = self.broker.place_market_order(
                        symbol=symbol,
                        quantity=quantity,
                        transaction_type=action,
                        price=price,
                        date=date
                    )
                    
                    if order_id:
                        self.trade_count += 1
    
    def track_portfolio_value(self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]):
        """
        Track daily portfolio value for performance analysis.
        """
        portfolio_value = self.broker.get_portfolio_value(price_data, date)
        self.portfolio_values.append((date, portfolio_value))
    
    def run_backtest(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Dict:
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
            current_value = self.broker.get_portfolio_value(price_data, date)
            pct_change = ((current_value - last_portfolio_value) / last_portfolio_value * 100) if last_portfolio_value > 0 else 0
            
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
                print("\n" + "="*80)
                if not initial_invested:
                    print(f"📅 INITIAL INVESTMENT ── {date.strftime('%Y-%m-%d')}   {'⚠️  WEAK MARKET' if is_weak_market else '💪 STRONG MARKET'}")
                else:
                    print(f"📅 REBALANCE SUMMARY ── {date.strftime('%Y-%m-%d')}   {'⚠️  WEAK MARKET' if is_weak_market else '💪 STRONG MARKET'}")
                print("="*80 + "\n")
                
                # Print portfolio snapshot
                print("📈 PORTFOLIO SNAPSHOT")
                print("─"*80)
                print(f"  DATE           : {date.strftime('%Y-%m-%d')}")
                print(f"  VALUE          : ₹{current_value:,.2f}")
                
                change_symbol = "▲" if pct_change > 0 else "▼" if pct_change < 0 else "▬"
                print(f"  CHANGE         : {change_symbol} {'+' if pct_change >= 0 else ''}{pct_change:.2f}%")
                print("─"*80 + "\n")
                
                if is_weak_market:
                    print("⚠️  All equity positions exited due to weak market regime.")
                    print("─"*80)
                elif not exec_df.empty:
                    print("🔄 TRADE ACTIONS")
                    print("─"*80)
                    
                    sells = exec_df[exec_df["Action"] == "SELL"]
                    buys = exec_df[exec_df["Action"] == "BUY"]
                    
                    if not sells.empty:
                        sold_symbols = sells["Symbol"].tolist()
                        print(f"  SOLD           : {wrap_symbols(sold_symbols)}\n")
                    
                    if not buys.empty:
                        bought_symbols = buys["Symbol"].tolist()
                        print(f"  BOUGHT         : {wrap_symbols(bought_symbols)}")
                    
                    print("─"*80)
                
                # Show current portfolio after rebalance
                current_holdings = self.broker.get_holdings()
                if current_holdings:
                    print("\n📊 STOCK PORTFOLIO")
                    print("─"*80)
                    portfolio_symbols = [holding["symbol"] for holding in current_holdings]
                    print(f"  HOLDINGS ({len(portfolio_symbols)})  : {wrap_symbols(portfolio_symbols)}")
                    print("─"*80)
                
                last_portfolio_value = current_value
                
                # Check if we've exited all positions due to weak market regime
                current_holdings = self.broker.get_holdings()
                if not current_holdings:
                    initial_invested = False
    
        # Generate and print results
        results = self._generate_results()
        self._print_summary(results)
        
        return results
    
    def _generate_results(self) -> Dict:
        """
        Generate performance metrics and results.
        """
        if not self.portfolio_values:
            return {}
        
        # Convert to DataFrame
        df_values = pd.DataFrame(self.portfolio_values, columns=["date", "portfolio_value"])
        df_values.set_index("date", inplace=True)
        
        # Calculate returns
        df_values["daily_return"] = df_values["portfolio_value"].pct_change()
        df_values["cumulative_return"] = (df_values["portfolio_value"] / self.initial_capital - 1) * 100
        
        # Performance metrics
        total_return = (df_values["portfolio_value"].iloc[-1] / self.initial_capital - 1) * 100
        
        # Annualized return (approximate)
        days = (df_values.index[-1] - df_values.index[0]).days
        years = days / 365.25
        cagr = ((df_values["portfolio_value"].iloc[-1] / self.initial_capital) ** (1/years) - 1) * 100 if years > 0 else 0
        
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
        
        return {
            "start_date": df_values.index[0],
            "end_date": df_values.index[-1],
            "initial_capital": self.initial_capital,
            "final_value": df_values["portfolio_value"].iloc[-1],
            "total_return_pct": total_return,
            "cagr_pct": cagr,
            "max_drawdown_pct": max_drawdown,
            "volatility_pct": volatility,
            "sharpe_ratio": sharpe_ratio,
            "total_trades": self.trade_count,
            "rebalance_count": len(self.rebalance_dates),
            "portfolio_values": df_values,
            "transactions": self.broker.get_transactions()
        }
    
    def _print_summary(self, results: Dict):
        """
        Print backtest summary.
        """
        print("\n" + "="*60)
        print("📈 BACKTEST RESULTS SUMMARY")
        print("="*60)
        print(f"🗓️  Period: {results['start_date'].date()} to {results['end_date'].date()}")
        print(f"💰 Initial Capital: ₹{results['initial_capital']:,.2f}")
        print(f"💎 Final Value: ₹{results['final_value']:,.2f}")
        print(f"📊 Total Return: {results['total_return_pct']:.2f}%")
        print(f"📈 CAGR: {results['cagr_pct']:.2f}%")
        print(f"📉 Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"📊 Volatility: {results['volatility_pct']:.2f}%")
        print(f"⚡ Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"🔄 Total Trades: {results['total_trades']}")
        print(f"📅 Rebalances: {results['rebalance_count']}")
        print("="*60)


def wrap_symbols(symbols: List[str], width: int = 65) -> str:
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

def run_backtest(start: str, end: str = None, rebalance_day: str = "Friday", band: int = 5):
    """
    Main entry point for backtesting from CLI.
    This function will be executed when you run `python cli.py backtest`
    
    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format (optional, defaults to last trading day)
        rebalance_day: Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)
        band: Band size for portfolio stability (higher = less churn)
    """
    start_date = pd.to_datetime(start)
    end_date = pd.to_datetime(end) if end else pd.to_datetime(get_last_trading_day())
    
    # Initialize and run backtest
    engine = BacktestEngine(
        initial_capital=10_00_000,  # Default 10 lakh
        top_n=15,
        band=band,
        rebalance_frequency="W",
        rebalance_day=rebalance_day
    )
    
    results = engine.run_backtest(start_date, end_date)
    
    # Save results to output folder
    if results:
        os.makedirs("output", exist_ok=True)
        
        # Save portfolio values
        results["portfolio_values"].to_csv(f"output/backtest-portfolio-{start}-{end_date.strftime('%Y-%m-%d')}.csv")
        
        # Save transactions
        transactions_df = results["transactions"]
        if not transactions_df.empty:
            transactions_df.to_csv(f"output/backtest-transactions-{start}-{end_date.strftime('%Y-%m-%d')}.csv", index=False)
        
        print(f"\n💾 Results saved to output/ folder")
    
    return results