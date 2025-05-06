from strategies.momentum_composite import MomentumComposite
import yfinance as yf

if __name__ == "__main__":
    config = {
        "universe": "nifty500",
        "start_date": "2018-12-01",           # for indicator warm-up
        "backtest_start_date": "2020-01-01",  # actual backtest start
        "initial_capital": 1_000_000,         # 💰 Starting portfolio value
        "benchmark": "^NSEI",
        "force_refresh": False
    }

    strategy = MomentumComposite(config)

    # Run backtest
    strategy.backtest(top_n=20, rebalance_frequency="ME")

    # Run on current date
    # strategy.run(top_n=20)

