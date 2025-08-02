import typer

from execution.backtest import run_backtest
from execution.live import run_rebalance, run_topup
from execution.maintenance import run_clean
from execution.portfolio import run_holdings_display, run_positions_display

app = typer.Typer(
    help="Xcelerator Alpha Strategy CLI - A momentum-based portfolio management system for Indian equities"
)


@app.command()
def rebalance(
    top_n: int = typer.Option(15, help="Number of stocks to select"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    cash: str = typer.Option("LIQUIDCASE", help="Cash equivalent symbol"),
    rank_day: str | None = typer.Option(
        None,
        help="Day of week for ranking (Monday, Tuesday, etc.). Default: use latest trading day",
    ),
    dry_run: bool = typer.Option(False, help="Simulate without placing orders"),
    universe: str = typer.Option("nifty500", help="Universe to use (nifty500, nifty100)"),
):
    """Run smart rebalancing strategy with market regime check"""
    run_rebalance(
        top_n=top_n, band=band, cash_equivalent=cash, rank_day=rank_day, dry_run=dry_run, universe=universe
    )


@app.command()
def topup(
    dry_run: bool = typer.Option(False, help="Simulate without placing orders"),
    universe: str = typer.Option("nifty500", help="Universe to use (nifty500, nifty100)"),
):
    """Add capital to existing portfolio"""
    run_topup(dry_run=dry_run, universe=universe)


@app.command()
def clean():
    """Delete all cached files and reset the strategy state."""
    run_clean()


@app.command()
def holdings(tsv: bool = False):
    """Display current holdings and their details."""
    run_holdings_display(tsv=tsv)


@app.command()
def positions(tsv: bool = False):
    """Display current positions and their details."""
    run_positions_display(tsv=tsv)


@app.command()
def backtest(
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(
        None, help="Optional end date (YYYY-MM-DD). Defaults to today."
    ),
    initial_capital: float = typer.Option(
        1_000_000, help="Initial capital for backtest (default ₹10 lakh)"
    ),
    rebalance_day: str = typer.Option(
        "Wednesday",
        help="Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)",
    ),
    band: int = typer.Option(
        5, help="Band size for portfolio stability (higher = less churn)"
    ),
    top_n: int = typer.Option(15, help="Number of stocks to select"),
    cash: str = typer.Option("LIQUIDCASE", help="Cash equivalent symbol"),
    universe: str = typer.Option("nifty500", help="Universe to use (nifty500, nifty100)"),
    rebalance_frequency: str = typer.Option(
        "W", help="Rebalance frequency (D for daily, W for weekly, M for monthly)"
    ),
):
    """Run the backtest for Xcelerator Alpha Strategy."""
    run_backtest(start, end, initial_capital, rebalance_day, band, top_n, cash, universe, rebalance_frequency)


if __name__ == "__main__":
    app()
