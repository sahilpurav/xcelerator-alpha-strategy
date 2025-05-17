from strategies.momentum_price_rsi import MomentumPriceRsiStrategy
from strategies.momentum_price_rsi_proximity import MomentumPriceRsiProximityStrategy
from strategies.momentum_price_proximity import MomentumPriceProximityStrategy
from strategies.momentum_rsi_proximity import MomentumRsiProximityStrategy
from strategies.momentum_pure_proximity import MomentumPureProximityStrategy
from strategies.momentum_pure_price import MomentumPurePriceStrategy
from strategies.momentum_pure_rsi import MomentumPureRsiStrategy

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

    # Store results in a dictionary for easier access
    results = {}

    # # Run the Momentum Price Proximity strategy
    # momentumPriceProximityStrategy = MomentumPriceProximityStrategy(config)
    # results["momentum_price_proximity"] = momentumPriceProximityStrategy.backtest(top_n=15, rebalance_frequency="W-THU")
    
    # # Run the Momentum Price RSI strategy
    # momentumPriceRsiStrategy = MomentumPriceRsiStrategy(config)
    # results["momentum_price_rsi"] = momentumPriceRsiStrategy.backtest(top_n=15, rebalance_frequency="W-THU")

    # # Run the Momentum Pure Price strategy
    # momentumPurePriceStrategy = MomentumPurePriceStrategy(config)
    # results["momentum_pure_price"] = momentumPurePriceStrategy.backtest(top_n=15, rebalance_frequency="W-THU")

    # # Run the Momentum Pure Proximity strategy
    # momentumPureProximityStrategy = MomentumPureProximityStrategy(config)
    # results["momentum_pure_proximity"] = momentumPureProximityStrategy.backtest(top_n=15, rebalance_frequency="W-THU")

    # # Run the Momentum Pure RSI strategy
    # momentumPureRsiStrategy = MomentumPureRsiStrategy(config)
    # results["momentum_pure_rsi"] = momentumPureRsiStrategy.backtest(top_n=15, rebalance_frequency="W-THU")

    # # Run the Momentum RSI Proximity strategy
    # momentumRsiProximityStrategy = MomentumRsiProximityStrategy(config)
    # results["momentum_rsi_proximity"] = momentumRsiProximityStrategy.backtest(top_n=15, rebalance_frequency="W-THU")

    #  Selecting the best strategy
    momentumPriceRsiProximityStrategy = MomentumPriceRsiProximityStrategy(config)

    # Running for current week
    # momentumPriceRsiProximityStrategy.run(15, band_threshold=5, prev_holdings=[
    #     "ADANIPORTS", "BDL", "BSE", "CEATLTD", "COROMANDEL", "ELECON", "GRSE", "INTELLECT", "JYOTICNC", "KAYNES", "MAZDOCK", "MOTILALOFS", "POONAWALLA", "RBLBANK", "REDINGTON"
    # ])

    # Run Backtest
    momentumPriceRsiProximityStrategy.backtest(top_n=15, rebalance_frequency="W-WED", band_threshold=5).summary()
