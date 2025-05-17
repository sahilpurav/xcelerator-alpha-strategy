import pandas as pd
import numpy as np
import os
from typing import Optional
from collections import defaultdict

class BacktestResult:
    def __init__(
        self,
        equity_curve: pd.Series,
        benchmark_curve: Optional[pd.Series] = None,
        rebalance_log: Optional[pd.DataFrame] = None,
        daily_equity_curve: Optional[pd.Series] = None
    ):
        self.equity = equity_curve
        self.benchmark = benchmark_curve
        self.rebalance_log = rebalance_log
        self.daily_equity_curve = daily_equity_curve

    def compute_cagr(self):
        start, end = self.equity.index[0], self.equity.index[-1]
        years = (end - start).days / 365.25
        return (self.equity.iloc[-1] / self.equity.iloc[0]) ** (1 / years) - 1

    def compute_max_drawdown(self, series=None):
        equity = series if series is not None else self.equity
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
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

    def compute_average_churn(self) -> float:
        if self.rebalance_log is None or self.rebalance_log.empty:
            return 0.0

        grouped = self.rebalance_log.groupby("Date")["Symbol"].apply(set)
        dates = grouped.index.tolist()

        churn_counts = []
        for i in range(1, len(dates)):
            prev = grouped.iloc[i - 1]
            curr = grouped.iloc[i]

            # Skip churn calc if either previous or current holding is empty or cash-only
            if "CASH" in prev or "CASH" in curr or len(prev) == 0 or len(curr) == 0:
                continue

            churn = len(prev - curr)
            churn_counts.append(churn)

        return round(sum(churn_counts) / len(churn_counts), 2) if churn_counts else 0.0
    
    def compute_daily_max_drawdown(self) -> float:
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None

        rolling_max = self.daily_equity_curve.cummax()
        drawdown = (self.daily_equity_curve - rolling_max) / rolling_max
        return drawdown.min()

    def compute_daily_max_gain(self) -> float:
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None

        daily_returns = self.daily_equity_curve.pct_change().dropna()
        return daily_returns.max()
    
    def compute_avg_daily_gain(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        return returns[returns > 0].mean()

    def compute_avg_daily_loss(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        return returns[returns < 0].mean()

    def compute_win_rate(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        return (returns > 0).mean()

    def compute_loss_rate(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        return (returns < 0).mean()

    def compute_daily_return_std(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        return returns.std()

    def compute_max_consecutive_wins(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        returns = self.daily_equity_curve.pct_change().dropna()
        win_streak, max_streak = 0, 0
        for r in returns:
            if r > 0:
                win_streak += 1
                max_streak = max(max_streak, win_streak)
            else:
                win_streak = 0
        return max_streak

    def compute_max_consecutive_losses(self):
        if self.daily_equity_curve is None or self.daily_equity_curve.empty:
            return None
        loss_streak, max_streak = 0, 0
        returns = self.daily_equity_curve.pct_change().dropna()
        for r in returns:
            if r < 0:
                loss_streak += 1
                max_streak = max(max_streak, loss_streak)
            else:
                loss_streak = 0
        return max_streak


    def compute_average_holding_period(self) -> float:
        if self.rebalance_log is None or self.rebalance_log.empty:
            return 0.0

        grouped = self.rebalance_log.groupby("Date")["Symbol"].apply(set)
        dates = grouped.index.tolist()
        date_to_idx = {date: i for i, date in enumerate(dates)}

        tracker = defaultdict(list)
        active = {}

        for date in dates:
            current = grouped[date]
            for s in current:
                if s not in active:
                    active[s] = date

            exited = set(active) - current
            for s in exited:
                tracker[s].append((active.pop(s), date))

        for s, d in active.items():
            tracker[s].append((d, dates[-1]))

        durations = [
            date_to_idx[exit_] - date_to_idx[entry]
            for periods in tracker.values()
            for entry, exit_ in periods
        ]

        return round(sum(durations) / len(durations), 2) if durations else 0.0

    def portfolio_summary(self) -> pd.DataFrame:
        return pd.DataFrame({
            "CAGR": [self.compute_cagr()],
            "Absolute Return": [self.compute_absolute_return()],
            "Max Drawdown": [self.compute_max_drawdown()],
            "Volatility": [self.compute_volatility()],
            "Sharpe Ratio": [self.compute_sharpe()],
            "Sortino Ratio": [self.compute_sortino()],
            "Alpha": [self.compute_alpha()],
            "Avg Churn/Rebalance": [self.compute_average_churn()],
            "Avg Holding Period": [self.compute_average_holding_period()],
            "Daily Max Drawdown": [self.compute_daily_max_drawdown()],
            "Daily Max Gain": [self.compute_daily_max_gain()],
            "Avg Daily Gain": [self.compute_avg_daily_gain()],
            "Avg Daily Loss": [self.compute_avg_daily_loss()],
            "Win Rate": [self.compute_win_rate()],
            "Loss Rate": [self.compute_loss_rate()],
            "Daily Return Std Dev": [self.compute_daily_return_std()],
            "Max Win Streak": [self.compute_max_consecutive_wins()],
            "Max Loss Streak": [self.compute_max_consecutive_losses()],
        })

    def benchmark_summary(self) -> pd.DataFrame:
        if self.benchmark is None or self.benchmark.empty:
            return pd.DataFrame()

        initial = self.benchmark.iloc[0]
        final = self.benchmark.iloc[-1]
        absolute_return = (final / initial) - 1
        cagr = (final / initial) ** (1 / ((self.benchmark.index[-1] - self.benchmark.index[0]).days / 365.25)) - 1
        volatility = self.benchmark.pct_change().std() * (252 ** 0.5)
        max_dd = self.compute_max_drawdown(self.benchmark)

        return pd.DataFrame({
            "CAGR": [round(cagr, 4)],
            "Absolute Return": [f"{absolute_return:.2%} ({(1 + absolute_return):.2f}x)"],
            "Max Drawdown": [round(max_dd, 4)],
            "Volatility": [round(volatility, 4)]
        })

    def to_csv(self, output_dir="reports/"):
        os.makedirs(output_dir, exist_ok=True)
        self.equity.to_csv(os.path.join(output_dir, "equity_curve.csv"), header=["Portfolio Value"], index_label="Date")
        if self.daily_equity_curve is not None:
            self.daily_equity_curve.to_csv(os.path.join(output_dir, "equity_curve_daily.csv"), header=["Portfolio Value"], index_label="Date")
        if self.rebalance_log is not None:
            self.rebalance_log.to_csv(os.path.join(output_dir, "rebalance_log.csv"), index=False)
