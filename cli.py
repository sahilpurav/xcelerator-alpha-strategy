import typer
from typing import Optional, List
from execution.live import run_rebalance, run_topup_only, run_withdraw
from execution.backtest import run_backtest
from execution.maintenance import run_clean
from execution.portfolio import run_holdings_display, run_positions_display, run_rank
from execution.optimization import run_optimize_weights, run_compare_weights

app = typer.Typer(help="Xcelerator Alpha Strategy CLI - A momentum-based portfolio management system for Indian equities")

@app.command()
def rebalance(
    top_n: int = typer.Option(15, help="Number of stocks to select"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    cash: str = typer.Option("LIQUIDCASE.NS", help="Cash equivalent symbol"),
    dry_run: bool = typer.Option(False, help="Simulate without placing orders")
):
    """Run full strategy with market regime check"""
    run_rebalance(top_n=top_n, band=band, cash_equivalent=cash, dry_run=dry_run)

@app.command()
def topup(
    amount: float = typer.Option(..., prompt="💰 Enter amount to add (₹)"),
    dry_run: bool = typer.Option(False, help="Simulate without placing orders")
):
    """Add capital to existing portfolio"""
    run_topup_only(amount=amount, dry_run=dry_run)

@app.command()
def withdraw(
    amount: Optional[float] = typer.Option(None, help="Amount to withdraw (₹)"),
    percent: Optional[float] = typer.Option(None, help="Percentage to withdraw (1-100)"),
    full: bool = typer.Option(False, help="Withdraw entire portfolio"),
    dry_run: bool = typer.Option(False, help="Simulate without placing orders")
):
    """Withdraw capital from portfolio"""
    run_withdraw(amount=amount, percentage=percent, full=full, dry_run=dry_run)

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
        end: Optional[str] = typer.Option(None, help="Optional end date (YYYY-MM-DD). Defaults to today."),
        rebalance_day: str = typer.Option("Wednesday", help="Day of week for rebalancing (Monday, Tuesday, Wednesday, Thursday, Friday)"),
        band: int = typer.Option(5, help="Band size for portfolio stability (higher = less churn)"),
        cash: str = typer.Option("LIQUIDBEES.NS", help="Cash equivalent symbol")
):
    """Run the backtest for Xcelerator Alpha Strategy."""
    run_backtest(start, end, rebalance_day, band, cash)


@app.command()
def optimize_weights(
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    method: str = typer.Option("grid", help="Optimization method: 'grid' or 'scipy'"),
    step: float = typer.Option(0.1, help="Grid search step size (0.05 for fine, 0.1 for coarse, 0.2 for quick)"),
    max_dd: float = typer.Option(-20.0, help="Maximum allowed drawdown percentage (e.g., -20.0 for -20%)"),
    top_n: int = typer.Option(15, help="Number of stocks in portfolio"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    save_results: bool = typer.Option(True, help="Save results to CSV file")
):
    """
    Optimize ranking weights for the momentum strategy.
    
    This command finds the optimal weights for return_rank, rsi_rank, and proximity_rank
    that maximize CAGR while keeping drawdown below the specified threshold.
    
    Examples:
        python cli.py optimize-weights --start 2020-01-01 --method grid --step 0.1
        python cli.py optimize-weights --start 2020-01-01 --method scipy --max-dd -20
    """
    
    run_optimize_weights(
        start=start,
        end=end,
        method=method,
        step=step,
        max_dd=max_dd,
        top_n=top_n,
        band=band,
        save_results=save_results
    )


@app.command()
def compare_weights(
    weights: List[str] = typer.Argument(..., help="Weight combinations to compare (e.g., '0.8,0.1,0.1' '0.6,0.2,0.2')"),
    start: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, help="End date (YYYY-MM-DD). Defaults to today."),
    max_dd: float = typer.Option(-20.0, help="Maximum allowed drawdown percentage"),
    top_n: int = typer.Option(15, help="Number of stocks in portfolio"),
    band: int = typer.Option(5, help="Band size for portfolio stability"),
    include_common: bool = typer.Option(False, help="Include common test combinations"),
    save_results: bool = typer.Option(True, help="Save results to CSV file")
):
    """
    Compare specific weight combinations for the momentum strategy.
    
    Examples:
        python cli.py compare-weights "0.8,0.1,0.1" "0.6,0.2,0.2" --start 2020-01-01
        python cli.py compare-weights "0.5,0.3,0.2" --start 2020-01-01 --include-common
    """
    
    run_compare_weights(
        weights=weights,
        start=start,
        end=end,
        max_dd=max_dd,
        top_n=top_n,
        band=band,
        include_common=include_common,
        save_results=save_results
    )

@app.command()
def rank(
    date: str = typer.Option(..., help="Date for ranking (YYYY-MM-DD)"),
    weights: str = typer.Option("0.8,0.1,0.1", help="Ranking weights as 'return,rsi,proximity' (must sum to 1.0)"),
    top_n: int = typer.Option(50, help="Number of top stocks to display"),
    save_results: bool = typer.Option(True, help="Save results to CSV file"),
    force_refresh: bool = typer.Option(False, help="Force cache refresh even if data exists")
):
    """
    Get stock rankings for a specific date.
    
    This command calculates momentum rankings for all stocks in the universe 
    for the specified date. It intelligently manages cache, ensuring 400 days 
    of historical data is available before the ranking date.
    
    Examples:
        python cli.py rank --date 2024-01-15
        python cli.py rank --date 2024-01-15 --weights "0.7,0.2,0.1" --top-n 30
        python cli.py rank --date 2024-01-15 --force-refresh
    """
    
    run_rank(
        date=date,
        weights=weights,
        top_n=top_n,
        save_results=save_results,
        force_refresh=force_refresh
    )

if __name__ == "__main__":
    app()
