from datetime import datetime as dt

def run_backtest_strategy(start: str, end: str = None):
    """
    Placeholder for backtest logic.
    This function will be executed when you run `python cli.py backtest`
    """
    start_date = dt.strptime(start, "%Y-%m-%d").date()
    end_date = dt.strptime(end, "%Y-%m-%d").date() if end else dt.today().date()

    print(f"✅ Backtest strategy execution started from {start_date} to {end_date}")