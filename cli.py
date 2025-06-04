import typer
import shutil
import os
from typing import Optional
from execution.live import run_initial_investment, run_rebalance, run_topup_only
from execution.backtest import run_backtest
from broker.zerodha import ZerodhaBroker
from logic.display import display_portfolio_table


app = typer.Typer()

@app.command()
def clear_cache():
    """
    Delete all cached files and reset the strategy state.
    This will remove all cached price data and reset the strategy state.
    """
    if os.path.exists("cache"):
        shutil.rmtree("cache")
        print("🗑️ Removed 'cache' folder.")
    if os.path.exists("output"):
        shutil.rmtree("output")
        print("🗑️ Removed 'output' folder.")
    else:
        print("✅ Nothing to delete.")

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
def rebalance(preview: bool = False, band: int = 5):
    """Run weekly rebalance with optional fresh capital"""
    run_rebalance(preview=preview, band=band)

@app.command()
def topup(amount: float = typer.Option(..., prompt="💰 Enter the total capital to top-up (amount in ₹)"), preview: bool = False):
    """Top up capital in current holdings only"""
    run_topup_only(amount, preview=preview)

@app.command()
def holdings(tsv: bool = False):
    """Display current holdings and their details."""
    broker = ZerodhaBroker()
    portfolio = broker.get_holdings()

    display_portfolio_table(
        portfolio,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
            "last_price": ("Close Price", 20),
        },
        tsv=tsv
    )

    
@app.command()
def positions(tsv: bool = False):
    """Display current positions and their details."""
    broker = ZerodhaBroker()
    positions = broker.get_current_positions()

    display_portfolio_table(
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
        end: Optional[str] = typer.Option(None, help="Optional end date (YYYY-MM-DD). Defaults to today."),
        rebalance_day: str = typer.Option("Friday", help="Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)"),
        band: int = typer.Option(5, help="Band size for portfolio stability (higher = less churn)")
):
    """
    Run the backtest for Xcelerator Alpha Strategy.

    Args:
        start (str): Start date in YYYY-MM-DD format.
        end (str): End date in YYYY-MM-DD format.
        rebalance_day (str): Day of week for rebalancing.
        band (int): Band size for portfolio stability (default 5).
    """
    run_backtest(start, end, rebalance_day, band)


if __name__ == "__main__":
    app()
