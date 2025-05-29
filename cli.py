import typer
import shutil
import os
from typing import Optional
from execution.live import run_initial_investment, run_rebalance, run_topup_only
from execution.backtest import run_backtest_strategy
from broker.zerodha import ZerodhaBroker
from logic.display import print_portfolio_table


app = typer.Typer()

@app.command()
def clear_cache():
    """
    Delete all cached files and reset the strategy state.
    This will remove all cached price data and reset the strategy state.
    """
    if os.path.exists("cache"):
        shutil.rmtree("cache")
        print("🗑️ Cache cleared.")
    else:
        print("✅ No cache folder found. Nothing to delete.")

@app.command()
def initial(
    top_n: int = typer.Option(15, prompt="📊 Enter number of stocks to invest in (top_n)"),
    amount: float = typer.Option(..., prompt="💰 Enter the total capital to invest (amount in ₹)")
):
    """
    Run initial investment interactively with prompts.
    """
    run_initial_investment(top_n=top_n, amount=amount)

@app.command()
def rebalance():
    """Run weekly rebalance with optional fresh capital"""
    run_rebalance()

@app.command()
def topup(amount: float = typer.Option(..., prompt="💰 Enter the total capital to top-up (amount in ₹)")):
    """Top up capital in current holdings only"""
    run_topup_only(amount)

@app.command()
def holdings():
    """Display current holdings and their details."""
    broker = ZerodhaBroker()
    portfolio = broker.get_holdings()

    print_portfolio_table(
        portfolio,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
        },
    )

    
@app.command()
def positions(tsv: bool = False):
    """Display current positions and their details."""
    broker = ZerodhaBroker()
    positions = broker.get_current_positions()

    print_portfolio_table(
        positions,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
        },
        tsv=tsv
    )


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
