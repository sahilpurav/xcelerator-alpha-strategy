from strategies.momentum_price_rsi_composite import MomentumPriceRsiComposite

if __name__ == "__main__":
    config = {
        "universe": "nifty500",
        "start_date": "2018-12-01",           # for indicator warm-up
        "backtest_start_date": "2020-01-01",  # actual backtest start
        "initial_capital": 1000000,         # 💰 Starting portfolio value
        "benchmark": "^NSEI",
        "force_refresh": False,
        "load_benchmark": True,
    }

    
    strategy = MomentumPriceRsiComposite(config)
    
    # Run backtest
    strategy.backtest(top_n=15, rebalance_frequency="W-FRI")

    # Run on current date
    # strategy.run(top_n=15)
