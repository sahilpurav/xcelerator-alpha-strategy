"""
Weight Optimization for Momentum Strategy

This module provides efficient weight optimization for the momentum ranking strategy.
"""

import os
from contextlib import redirect_stdout
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .engines import WeightedBacktestEngine


class WeightOptimizer:
    """
    Optimizes ranking weights for the momentum strategy.
    """

    def __init__(
        self,
        start_date: str = "2020-01-01",
        end_date: str = "2023-12-31",
        max_drawdown_threshold: float = -20.0,
        top_n: int = 15,
        band: int = 5,
        initial_capital: float = 10_00_000,
        rebalance_frequency: str = "W",
        rebalance_day: str = "Wednesday",
    ):
        """
        Initialize the weight optimizer.

        Args:
            start_date: Backtest start date in YYYY-MM-DD format
            end_date: Backtest end date in YYYY-MM-DD format
            max_drawdown_threshold: Maximum allowed drawdown (e.g., -20.0 for -20%)
            top_n: Number of stocks in portfolio
            band: Band size for portfolio stability
            initial_capital: Starting capital
            rebalance_frequency: 'W' for weekly, 'M' for monthly
            rebalance_day: Day of week for rebalancing
        """
        self.start_date = start_date
        self.end_date = end_date
        self.max_drawdown_threshold = max_drawdown_threshold
        self.top_n = top_n
        self.band = band
        self.initial_capital = initial_capital
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_day = rebalance_day

        # Convert dates
        self.start_dt = pd.to_datetime(start_date)
        self.end_dt = pd.to_datetime(end_date)

    def run_backtest_with_weights(
        self, weights: Tuple[float, float, float], verbose: bool = False
    ) -> Optional[Dict]:
        """
        Run backtest with specific weights using the modified ranking function.
        """
        try:
            # Create custom backtest engine that uses weights
            engine = WeightedBacktestEngine(
                weights=weights,
                initial_capital=self.initial_capital,
                top_n=self.top_n,
                band=self.band,
                rebalance_frequency=self.rebalance_frequency,
                rebalance_day=self.rebalance_day,
            )

            if not verbose:
                # Suppress output
                with open(os.devnull, "w") as devnull:
                    with redirect_stdout(devnull):
                        results = engine.run_backtest(self.start_dt, self.end_dt)
            else:
                results = engine.run_backtest(self.start_dt, self.end_dt)

            return results

        except Exception as e:
            if verbose:
                print(f"Error in backtest with weights {weights}: {e}")
            return None

    def grid_search(self, weight_step: float = 0.1, verbose: bool = True) -> Dict:
        """
        Optimize weights using grid search.
        """
        # Generate weight combinations that sum to 1.0
        weights = []
        step = int(1.0 / weight_step)

        for w1 in range(0, step + 1):
            for w2 in range(0, step + 1 - w1):
                w3 = step - w1 - w2
                if w3 >= 0:
                    weights.append(
                        (w1 * weight_step, w2 * weight_step, w3 * weight_step)
                    )

        if verbose:
            print(f"🔍 Grid Search Weight Optimization")
            print(f"=" * 80)
            print(f"📅 Period: {self.start_date} to {self.end_date}")
            print(f"🎯 Max Drawdown Threshold: {self.max_drawdown_threshold}%")
            print(f"📊 Portfolio: {self.top_n} stocks, Band: {self.band}")
            print(
                f"🔢 Testing {len(weights)} weight combinations (step: {weight_step})"
            )
            print(f"=" * 80)
            print(f"{'#':<4} {'Weights':<20} {'CAGR%':<8} {'MaxDD%':<8} {'Status':<20}")
            print(f"=" * 80)

        results = []
        best_cagr = -float("inf")
        best_weights = None
        best_result = None
        valid_count = 0
        rejected_count = 0

        for i, (w1, w2, w3) in enumerate(weights):
            if verbose:
                weights_str = f"({w1:.1f},{w2:.1f},{w3:.1f})"
                print(f"{i+1:<4} {weights_str:<20}", end="")

            result = self.run_backtest_with_weights((w1, w2, w3), verbose=False)

            if result is None:
                if verbose:
                    print(f"{'N/A':<8} {'N/A':<8} {'❌ FAILED':<20}")
                continue

            cagr = result.get("cagr_pct", 0)
            max_dd = result.get("max_drawdown_pct", 0)

            # Store result
            result_record = {
                "return_weight": w1,
                "rsi_weight": w2,
                "proximity_weight": w3,
                "cagr": cagr,
                "max_drawdown": max_dd,
                "meets_constraint": max_dd >= self.max_drawdown_threshold,
                "total_return": result.get("total_return_pct", 0),
                "volatility": result.get("volatility_pct", 0),
                "sharpe_ratio": result.get("sharpe_ratio", 0),
                "total_trades": result.get("total_trades", 0),
            }

            results.append(result_record)

            # Check constraint and display status
            if max_dd >= self.max_drawdown_threshold:
                valid_count += 1
                # Check if this is the best valid combination
                if cagr > best_cagr:
                    best_cagr = cagr
                    best_weights = (w1, w2, w3)
                    best_result = result

                    if verbose:
                        print(f"{cagr:<8.2f} {max_dd:<8.2f} {'🏆 NEW BEST!':<20}")
                else:
                    if verbose:
                        print(f"{cagr:<8.2f} {max_dd:<8.2f} {'✅ Valid':<20}")
            else:
                rejected_count += 1
                if verbose:
                    print(f"{cagr:<8.2f} {max_dd:<8.2f} {'❌ DD Exceeded':<20}")

            # Progress update every 10 combinations
            if verbose and (i + 1) % 10 == 0:
                print(f"-" * 80)
                progress_pct = (i + 1) / len(weights) * 100
                print(
                    f"📊 Progress: {i + 1}/{len(weights)} ({progress_pct:.1f}%) | "
                    f"Valid: {valid_count} | Rejected: {rejected_count}"
                )
                if best_weights:
                    print(f"🏆 Current Best: {best_weights} → CAGR: {best_cagr:.2f}%")
                print(f"-" * 80)

        # Convert results to DataFrame for analysis
        results_df = pd.DataFrame(results)

        if verbose:
            self._print_optimization_results(
                results_df,
                best_weights,
                best_cagr,
                best_result,
                valid_count,
                rejected_count,
                len(weights),
            )

        return {
            "best_weights": best_weights,
            "best_cagr": best_cagr,
            "best_result": best_result,
            "all_results": results_df,
            "valid_combinations": valid_count,
            "total_tested": len(results),
            "rejected_combinations": rejected_count,
        }

    def scipy_optimize(self, verbose: bool = True) -> Dict:
        """
        Optimize weights using scipy.optimize.
        """
        try:
            from scipy.optimize import minimize
        except ImportError:
            raise ImportError(
                "scipy is required for this optimization method. Install with: pip install scipy"
            )

        if verbose:
            print("🔬 Scipy Weight Optimization")
            print("=" * 60)
            print(f"📅 Period: {self.start_date} to {self.end_date}")
            print(f"🎯 Max Drawdown Threshold: {self.max_drawdown_threshold}%")
            print("=" * 60)

        def objective(weights):
            """Objective function to minimize (negative CAGR)"""
            result = self.run_backtest_with_weights(tuple(weights), verbose=False)

            if result is None:
                return 1000  # Large penalty for failed backtests

            cagr = result.get("cagr_pct", 0)
            max_dd = result.get("max_drawdown_pct", 0)

            # Penalty if max drawdown constraint is violated
            if max_dd < self.max_drawdown_threshold:
                penalty = abs(max_dd - self.max_drawdown_threshold) * 100
                return -cagr + penalty

            return -cagr  # Minimize negative CAGR (maximize CAGR)

        # Constraints: weights sum to 1, each weight >= 0
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]  # Sum equals 1

        bounds = [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0)]  # Each weight between 0 and 1

        # Initial guess (current weights)
        x0 = [0.8, 0.1, 0.1]

        if verbose:
            print(f"🚀 Starting optimization from weights: {x0}")

        # Run optimization
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 100, "disp": verbose},
        )

        if result.success:
            best_weights = tuple(result.x)

            # Get detailed results for best weights
            best_result = self.run_backtest_with_weights(best_weights, verbose=False)

            if verbose:
                print("\n" + "=" * 60)
                print("🎯 OPTIMIZATION RESULTS")
                print("=" * 60)
                print(
                    f"🏆 Optimal weights: Return={best_weights[0]:.3f}, "
                    f"RSI={best_weights[1]:.3f}, Proximity={best_weights[2]:.3f}"
                )
                if best_result:
                    print(f"📈 CAGR: {best_result['cagr_pct']:.2f}%")
                    print(f"📉 Max Drawdown: {best_result['max_drawdown_pct']:.2f}%")
                    print(f"📊 Sharpe Ratio: {best_result.get('sharpe_ratio', 0):.2f}")

            return {
                "best_weights": best_weights,
                "best_cagr": best_result["cagr_pct"] if best_result else None,
                "best_result": best_result,
                "optimization_result": result,
                "success": True,
            }
        else:
            if verbose:
                print(f"❌ Optimization failed: {result.message}")

            return {
                "best_weights": None,
                "best_cagr": None,
                "best_result": None,
                "optimization_result": result,
                "success": False,
            }

    def compare_combinations(
        self, combinations: List[Tuple[float, float, float]]
    ) -> pd.DataFrame:
        """
        Compare specific weight combinations.
        """
        results = []

        print(f"🔍 Comparing Weight Combinations")
        print(f"=" * 80)
        print(f"📅 Period: {self.start_date} to {self.end_date}")
        print(f"🎯 Max Drawdown Threshold: {self.max_drawdown_threshold}%")
        print(f"📊 Testing {len(combinations)} combinations")
        print(f"=" * 80)
        print(
            f"{'#':<3} {'Weights':<20} {'CAGR%':<8} {'MaxDD%':<8} {'Sharpe':<7} {'Status':<15}"
        )
        print(f"=" * 80)

        for i, weights in enumerate(combinations):
            result = self.run_backtest_with_weights(weights, verbose=False)

            if result:
                cagr = result.get("cagr_pct", 0)
                max_dd = result.get("max_drawdown_pct", 0)
                sharpe = result.get("sharpe_ratio", 0)
                meets_constraint = max_dd >= self.max_drawdown_threshold
                status = "✅ Valid" if meets_constraint else "❌ DD Exceeded"

                weights_str = f"({weights[0]:.1f},{weights[1]:.1f},{weights[2]:.1f})"
                print(
                    f"{i+1:<3} {weights_str:<20} {cagr:<8.2f} {max_dd:<8.2f} {sharpe:<7.2f} {status:<15}"
                )

                results.append(
                    {
                        "return_weight": weights[0],
                        "rsi_weight": weights[1],
                        "proximity_weight": weights[2],
                        "cagr": cagr,
                        "max_drawdown": max_dd,
                        "total_return": result.get("total_return_pct", 0),
                        "volatility": result.get("volatility_pct", 0),
                        "sharpe_ratio": sharpe,
                        "total_trades": result.get("total_trades", 0),
                        "meets_constraint": meets_constraint,
                    }
                )
            else:
                weights_str = f"({weights[0]:.1f},{weights[1]:.1f},{weights[2]:.1f})"
                print(
                    f"{i+1:<3} {weights_str:<20} {'N/A':<8} {'N/A':<8} {'N/A':<7} {'❌ Failed':<15}"
                )

        results_df = pd.DataFrame(results)

        if not results_df.empty:
            # Sort by CAGR (descending) for valid combinations first
            results_df = results_df.sort_values(
                ["meets_constraint", "cagr"], ascending=[False, False]
            )

            print(f"\n📊 COMPARISON SUMMARY")
            print(f"=" * 80)
            valid_count = len(results_df[results_df["meets_constraint"] == True])
            print(f"✅ Valid combinations: {valid_count}/{len(results_df)}")

            if valid_count > 0:
                best = results_df[results_df["meets_constraint"] == True].iloc[0]
                print(
                    f"🏆 Best combination: ({best['return_weight']:.1f}, {best['rsi_weight']:.1f}, {best['proximity_weight']:.1f})"
                )
                print(
                    f"   CAGR: {best['cagr']:.2f}% | Max DD: {best['max_drawdown']:.2f}% | Sharpe: {best['sharpe_ratio']:.2f}"
                )

        return results_df

    def _print_optimization_results(
        self,
        results_df,
        best_weights,
        best_cagr,
        best_result,
        valid_count,
        rejected_count,
        total_combinations,
    ):
        """Print comprehensive optimization results."""
        print(f"\n" + "=" * 80)
        print(f"🎯 OPTIMIZATION COMPLETE")
        print(f"=" * 80)

        print(f"📊 SUMMARY:")
        print(f"   Total combinations tested: {total_combinations}")
        print(f"   ✅ Valid (met constraint): {valid_count}")
        print(f"   ❌ Rejected (DD exceeded): {rejected_count}")
        print(f"   Success Rate: {valid_count/total_combinations*100:.1f}%")

        if best_weights:
            print(f"\n🏆 OPTIMAL WEIGHTS FOUND:")
            print(f"   Return Weight: {best_weights[0]:.1f}")
            print(f"   RSI Weight: {best_weights[1]:.1f}")
            print(f"   Proximity Weight: {best_weights[2]:.1f}")
            print(f"\n📈 PERFORMANCE:")
            print(f"   CAGR: {best_cagr:.2f}%")
            if best_result:
                print(f"   Max Drawdown: {best_result.get('max_drawdown_pct', 0):.2f}%")
                print(f"   Total Return: {best_result.get('total_return_pct', 0):.2f}%")
                print(f"   Sharpe Ratio: {best_result.get('sharpe_ratio', 0):.2f}")
                print(f"   Volatility: {best_result.get('volatility_pct', 0):.2f}%")
                print(f"   Total Trades: {best_result.get('total_trades', 0)}")

            # Compare with current strategy (0.8, 0.1, 0.1)
            current_result = self.run_backtest_with_weights(
                (0.8, 0.1, 0.1), verbose=False
            )
            if current_result:
                current_cagr = current_result.get("cagr_pct", 0)
                improvement = best_cagr - current_cagr
                print(f"\n📊 COMPARISON WITH CURRENT STRATEGY:")
                print(f"   Current weights (0.8, 0.1, 0.1): {current_cagr:.2f}% CAGR")
                print(f"   Optimal weights: {best_cagr:.2f}% CAGR")
                print(f"   Improvement: {improvement:+.2f}% CAGR")
        else:
            print(f"\n❌ NO VALID COMBINATIONS FOUND!")
            print(
                f"   All tested combinations exceeded the max drawdown threshold of {self.max_drawdown_threshold}%"
            )
            print(f"\n💡 SUGGESTIONS:")
            print(f"   • Try relaxing the max drawdown threshold (e.g., -25% or -30%)")
            print(f"   • Test different time periods")
            print(f"   • Adjust portfolio parameters (top_n, band)")

        print(f"=" * 80)
