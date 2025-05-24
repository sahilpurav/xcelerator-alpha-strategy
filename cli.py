import typer
import shutil
import os
from typing import Optional
from execution.run_live import run_live_strategy
from execution.run_backtest import run_backtest_strategy


app = typer.Typer()

@app.command()
def clear_cache():
    """Delete all cached files and reset the strategy state."""
    if os.path.exists("cache"):
        shutil.rmtree("cache")
        print("🗑️ Cache cleared.")
    else:
        print("✅ No cache folder found. Nothing to delete.")

@app.command()
def live():
    """
    Run the live rebalance for Xcelerator Alpha Strategy.
    Fetches latest prices, filters stocks, ranks, and prints final portfolio.
    """
    run_live_strategy()


@app.command()
def backtest(
        start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
        end: Optional[str] = typer.Option(None, help="Optional end date (YYYY-MM-DD). Defaults to today.")
):
    """
    Run the backtest for Xcelerator Alpha Strategy.

    Args:
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.
    """
    run_backtest_strategy(start, end)


if __name__ == "__main__":
    app()
