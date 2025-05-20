from strategies.momentum_price_rsi_proximity import MomentumPriceRsiProximityStrategy

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

    #  Selecting the best strategy
    momentumPriceRsiProximityStrategy = MomentumPriceRsiProximityStrategy(config)

    # Running for current week
    momentumPriceRsiProximityStrategy.run(15, band_threshold=5, prev_holdings=[
        "ADANIPORTS", "BDL", "BSE", "CEATLTD", "COROMANDEL", "ELECON", "GRSE", "INTELLECT", "JYOTICNC", "KAYNES", "MAZDOCK", "MOTILALOFS", "POONAWALLA", "RBLBANK", "REDINGTON"
    ])

    # Run Backtest
    # momentumPriceRsiProximityStrategy.backtest(top_n=15, rebalance_frequency="W-WED", band_threshold=5).summary()
