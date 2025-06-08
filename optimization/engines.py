"""
Custom backtest engines for weight optimization.
"""

import pandas as pd
from typing import Tuple, Dict, List
from execution.backtest import BacktestEngine
from logic.ranking import rank
from logic.planner import plan_initial_investment, plan_rebalance_investment, plan_exit_all_positions
from logic.strategy import generate_band_adjusted_portfolio
from utils.market import is_market_strong


class WeightedBacktestEngine(BacktestEngine):
    """
    Extended BacktestEngine that uses custom weights for ranking.
    """
    
    def __init__(self, weights: Tuple[float, float, float], **kwargs):
        """
        Initialize with custom ranking weights.
        
        Args:
            weights: Tuple of (return_weight, rsi_weight, proximity_weight)
            **kwargs: Other BacktestEngine parameters
        """
        super().__init__(**kwargs)
        self.weights = weights
    
    def get_ranked_stocks(self, price_data: Dict[str, pd.DataFrame], as_of_date: pd.Timestamp) -> pd.DataFrame:
        """
        Override to use custom weights for ranking.
        This replaces the strategy.get_ranked_stocks function with weighted ranking.
        """
        benchmark_df = price_data.get("^CRSLDX")
        
        if benchmark_df is None:
            raise ValueError("Benchmark data (^CRSLDX) not found in price data.")

        benchmark_df = benchmark_df[benchmark_df.index <= as_of_date]

        if not is_market_strong(benchmark_df):
            return pd.DataFrame()

        # Apply ranking logic with custom weights
        ranked = rank(price_data, as_of_date, weights=self.weights)

        ranked["rank"] = ranked["total_rank"].rank(method="first").astype(int)
        return ranked  # return full list
    
    def execute_initial_investment(self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]) -> Tuple[bool, pd.DataFrame]:
        """
        Execute initial investment using custom weighted ranking.
        """
        # Get ranked stocks using custom weights
        ranked_df = self.get_ranked_stocks(price_data, date)
        
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
            total_capital=self.initial_capital,
            ranked_df=ranked_df
        )
        
        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)
        
        return True, exec_df
    
    def execute_rebalance(self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]) -> Tuple[bool, pd.DataFrame]:
        """
        Execute rebalancing using custom weighted ranking.
        """
        # Get current holdings
        previous_holdings = self.broker.get_holdings()
        held_symbols = [h["symbol"] for h in previous_holdings]
        
        if not held_symbols:
            return False, pd.DataFrame()
        
        # Get ranked stocks using custom weights
        ranked_df = self.get_ranked_stocks(price_data, date)
        
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
