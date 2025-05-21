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
    previous_holdings = [
        { "symbol": "ADANIPORTS", "quantity": 83, "price": 1384.00 },
        { "symbol": "BDL", "quantity": 71 },
        { "symbol": "BSE", "quantity": 15 },
        { "symbol": "CEATLTD", "quantity": 30 },
        { "symbol": "COROMANDEL", "quantity": 45 },
        { "symbol": "ELECON", "quantity": 174 },
        { "symbol": "GRSE", "quantity": 61 },
        { "symbol": "INTELLECT", "quantity": 125 },
        { "symbol": "JYOTICNC", "quantity": 94, "price": 1194.00 },
        { "symbol": "KAYNES", "quantity": 18, "price": 5895.50 },
        { "symbol": "MAZDOCK", "quantity": 38 },
        { "symbol": "MOTILALOFS", "quantity": 154, "price": 775.55 },
        { "symbol": "POONAWALLA", "quantity": 294, "price": 394.35 },
        { "symbol": "RBLBANK", "quantity": 530, "price": 210.10 },
        { "symbol": "REDINGTON", "quantity": 409 },
    ]
    momentumPriceRsiProximityStrategy.run(15, band_threshold=5, previous_holdings=previous_holdings)

    # Run Backtest
    # momentumPriceRsiProximityStrategy.backtest(top_n=15, rebalance_frequency="W-WED", band_threshold=5).summary()
