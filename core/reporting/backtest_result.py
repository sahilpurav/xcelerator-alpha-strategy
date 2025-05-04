import pandas as pd
import numpy as np
import os
from typing import Optional

class BacktestResult:
    def __init__(
        self,
        equity_curve: pd.Series,
        benchmark_curve: Optional[pd.Series] = None,
        rebalance_log: Optional[pd.DataFrame] = None,
    ):
        self.equity = equity_curve
        self.benchmark = benchmark_curve
        self.rebalance_log = rebalance_log

    def compute_cagr(self):
        start, end = self.equity.index[0], self.equity.index[-1]
        years = (end - start).days / 365.25
        return (self.equity.iloc[-1] / self.equity.iloc[0]) ** (1 / years) - 1

    def compute_max_drawdown(self):
        roll_max = self.equity.cummax()
        drawdown = (self.equity - roll_max) / roll_max
        return drawdown.min()

    def compute_volatility(self):
        returns = self.equity.pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def compute_sharpe(self, risk_free_rate=0.05):
        returns = self.equity.pct_change().dropna()
        excess = returns - (risk_free_rate / 252)
        return (excess.mean() / excess.std()) * np.sqrt(252)

    def compute_sortino(self, risk_free_rate=0.05):
        returns = self.equity.pct_change().dropna()
        downside = returns[returns < 0]
        if downside.std() == 0:
            return np.nan
        excess = returns - (risk_free_rate / 252)
        return (excess.mean() / downside.std()) * np.sqrt(252)

    def compute_alpha(self):
        if self.benchmark is None:
            return None
        strategy_return = self.compute_cagr()
        bench_return = (self.benchmark.iloc[-1] / self.benchmark.iloc[0]) ** (1 / ((self.benchmark.index[-1] - self.benchmark.index[0]).days / 365.25)) - 1
        return strategy_return - bench_return
    
    def compute_absolute_return(self):
        initial = self.equity.iloc[0]
        final = self.equity.iloc[-1]
        return (final / initial) - 1

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame({
            "CAGR": [self.compute_cagr()],
            "Absolute Return": [self.compute_absolute_return()],
            "Max Drawdown": [self.compute_max_drawdown()],
            "Volatility": [self.compute_volatility()],
            "Sharpe Ratio": [self.compute_sharpe()],
            "Sortino Ratio": [self.compute_sortino()],
            "Alpha": [self.compute_alpha()]
        })

    def to_csv(self, output_dir="reports/"):
        os.makedirs(output_dir, exist_ok=True)
        self.equity.to_csv(os.path.join(output_dir, "equity_curve.csv"))
        if self.rebalance_log is not None:
            self.rebalance_log.to_csv(os.path.join(output_dir, "rebalance_log.csv"), index=False)
