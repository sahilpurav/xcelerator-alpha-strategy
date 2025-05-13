from strategies.momentum_all_composite import MomentumAllComposite
from strategies.momentum_pure_price import MomentumPurePrice
from strategies.momentum_pure_rsi import MomentumPureRsi
from strategies.momentum_pure_high_proximity import MomentumPureHighProximity
from strategies.momentum_price_rsi_composite import MomentumPriceRsiComposite
from strategies.momentum_price_high_proximity_composite import MomentumPriceHighProximityComposite
from strategies.momentum_rsi_high_proximity_composite import MomentumRsiHighProximityComposite
from core.stock import Stock

if __name__ == "__main__":
    config = {
        "universe": "nifty500",
        "start_date": "2018-12-01",           # for indicator warm-up
        "backtest_start_date": "2020-01-01",  # actual backtest start
        "initial_capital": 100000,         # 💰 Starting portfolio value
        "benchmark": "^NSEI",
        "force_refresh": False,
        "load_benchmark": True,
    }

    # strategy = MomentumAllComposite(config)
    # strategy = MomentumPurePrice(config)
    # strategy = MomentumPureRsi(config)
    # strategy = MomentumPureHighProximity(config)
    strategy = MomentumPriceRsiComposite(config)
    # strategy = MomentumPriceHighProximityComposite(config)
    # strategy = MomentumRsiHighProximityComposite(config)

    # Run backtest
    strategy.backtest(top_n=15, rebalance_frequency="W")

    # Run on current date
    # strategy.run(top_n=15)
