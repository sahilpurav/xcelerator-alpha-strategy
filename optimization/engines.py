"""
Custom backtest engines for weight optimization.
"""

from typing import Dict, List, Tuple

import pandas as pd

from execution.backtest import BacktestEngine
from logic.planner import (
    plan_equity_investment,
    plan_move_to_cash_equivalent,
    plan_portfolio_rebalance,
)
from logic.ranking import rank
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

    def run_strategy(
        self,
        price_data: Dict[str, pd.DataFrame],
        as_of_date: pd.Timestamp,
        held_symbols: List[str],
        top_n: int,
        band: int,
    ) -> Tuple[List[str], List[str], List[str], List[str], pd.DataFrame]:
        """
        Custom run_strategy that uses weighted ranking.
        Complete strategy execution: market filter + ranking + portfolio construction.
        """
        # Step 1: Check market strength
        if not is_market_strong(
            price_data, benchmark_symbol="^CRSLDX", as_of_date=as_of_date
        ):
            return (
                [],
                [],
                held_symbols,
                [],
                pd.DataFrame(),
            )  # Exit all positions in weak market

        # Step 2: Rank stocks with custom weights
        ranked_df = rank(price_data, as_of_date, weights=self.weights)
        ranked_df["rank"] = ranked_df["total_rank"].rank(method="first").astype(int)

        # Step 3: Apply band logic for portfolio construction
        ranked_df_work = ranked_df.reset_index(drop=True)
        ranked_df_work["rank"] = ranked_df_work.index + 1
        ranked_df_work["symbol"] = ranked_df_work["symbol"].str.replace(
            ".NS", "", regex=False
        )
        symbols_ranked = ranked_df_work["symbol"].tolist()

        held_stocks = []
        removed_stocks = []

        # Check which held stocks to keep or remove
        for sym in held_symbols:
            if sym in symbols_ranked:
                rank_pos = ranked_df_work.loc[
                    ranked_df_work["symbol"] == sym, "rank"
                ].values[0]
                if rank_pos <= top_n + band:
                    held_stocks.append(sym)
                else:
                    removed_stocks.append(sym)
            else:
                removed_stocks.append(sym)

        # Determine new entries
        top_n_symbols = ranked_df_work.head(top_n)["symbol"].tolist()
        new_entries = [s for s in top_n_symbols if s not in held_stocks][
            : top_n - len(held_stocks)
        ]
        final_portfolio = held_stocks + new_entries

        return held_stocks, new_entries, removed_stocks, final_portfolio, ranked_df

    def execute_initial_investment(
        self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[bool, pd.DataFrame]:
        """
        Execute initial investment using custom weighted ranking.
        """
        # Run strategy to get ranked stocks using custom weights
        _, _, _, _, ranked_df = self.run_strategy(
            price_data, date, [], self.top_n, self.band
        )

        if ranked_df.empty:
            return False, pd.DataFrame()

        # Select top N stocks
        top_n_df = ranked_df.nsmallest(self.top_n, "total_rank")
        selected_symbols = top_n_df["symbol"].tolist()

        # Generate execution plan
        exec_df = plan_equity_investment(
            symbols=selected_symbols,
            price_data=price_data,
            as_of_date=date,
            total_capital=self.initial_capital,
            ranked_df=ranked_df,
        )

        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)

        return True, exec_df

    def execute_rebalance(
        self, date: pd.Timestamp, price_data: Dict[str, pd.DataFrame]
    ) -> Tuple[bool, pd.DataFrame]:
        """
        Execute rebalancing using custom weighted ranking.
        """
        # Get current holdings
        previous_holdings = self.broker.get_holdings()
        held_symbols = [h["symbol"] for h in previous_holdings]

        if not held_symbols:
            return False, pd.DataFrame()

        # Run strategy to determine portfolio changes using custom weights
        held, new_entries, removed, _, ranked_df = self.run_strategy(
            price_data, date, held_symbols, self.top_n, self.band
        )

        # Check if we need to exit all positions (weak market)
        if not held and not new_entries and removed == held_symbols:
            # Plan complete exit
            exec_df = plan_move_to_cash_equivalent(
                previous_holdings=previous_holdings,
                price_data=price_data,
                as_of_date=date,
                ranked_df=pd.DataFrame(),  # Empty DataFrame for weak regime
            )

            # Execute exit trades
            if not exec_df.empty:
                self._execute_backtest_orders(exec_df, date, price_data)
            return False, exec_df

        if not new_entries and not removed:
            return True, pd.DataFrame()

        # Generate execution plan
        exec_df = plan_portfolio_rebalance(
            held_stocks=held,
            new_entries=new_entries,
            removed_stocks=removed,
            previous_holdings=previous_holdings,
            price_data=price_data,
            as_of_date=date,
            ranked_df=ranked_df,
            transaction_cost_pct=self.transaction_cost_pct,
        )

        # Execute trades
        self._execute_backtest_orders(exec_df, date, price_data)

        return True, exec_df
