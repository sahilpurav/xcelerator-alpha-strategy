from strategies.momentum_price_rsi_proximity import MomentumPriceRsiProximityStrategy
from core.brokers import ZerodhaBroker
import pytz
from datetime import datetime, timedelta

if __name__ == "__main__":

    config = {
        "universe": "nifty500",
        "start_date": "2018-12-01",           # for indicator warm-up
        "backtest_start_date": "2020-01-01",  # actual backtest start
        "initial_capital": 1000000,         # 💰 Starting portfolio value
        "benchmark": "^NSEI",
        "force_refresh": False,
        "load_benchmark": True,
        "backtest_mode": False,
    }

    if config["backtest_mode"]:
        strategy = MomentumPriceRsiProximityStrategy(config)
        strategy.backtest(top_n=15, rebalance_frequency="W-WED", band_threshold=5).summary()
    else:
        # Set the start date to 400 days before today
        india_tz = pytz.timezone("Asia/Kolkata")
        now = datetime.now(india_tz)
        config["start_date"] = (now - timedelta(days=400)).strftime('%Y-%m-%d')
        
        broker = ZerodhaBroker()
        broker.connect()

        # Running for current week
        previous_holdings = [
            {"symbol": h["tradingsymbol"], "quantity": h["quantity"]}
            for h in broker.get_holdings()
        ]

        # Run the strategy for the current week
        strategy = MomentumPriceRsiProximityStrategy(config)
        strategy.run(15, band_threshold=5, previous_holdings=previous_holdings)