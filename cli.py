import typer
from typing import Optional, List
from execution.live import run_initial_investment, run_rebalance, run_topup_only
from execution.backtest import run_backtest
from execution.maintenance import run_clear_cache
from execution.portfolio import run_holdings_display, run_positions_display, run_rank
from execution.optimization import run_optimize_weights, run_compare_weights

app = typer.Typer()

@app.command()
def initial(
    top_n: int = typer.Option(15, prompt="📊 Enter number of stocks to invest in (top_n)"),
    amount: float = typer.Option(..., prompt="💰 Enter the total capital to invest (amount in ₹)")
):
    """Run initial investment interactively with prompts."""
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
def clean():
    """Delete all cached files and reset the strategy state."""
    run_clear_cache()

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
        band: int = typer.Option(5, help="Band size for portfolio stability (higher = less churn)")
):
    """Run the backtest for Xcelerator Alpha Strategy."""
    run_backtest(start, end, rebalance_day, band)


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
