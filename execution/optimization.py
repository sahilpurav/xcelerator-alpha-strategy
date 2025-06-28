import os
from datetime import datetime

import typer

from optimization import WeightOptimizer
from optimization.utils import (
    generate_test_combinations,
    parse_weights_string,
    save_optimization_results,
)
from utils.cache import save_to_file


def run_optimize_weights(
    start: str,
    end: str | None,
    method: str,
    step: float,
    max_dd: float,
    top_n: int,
    band: int,
    save_results: bool,
):
    """Run weight optimization using grid search or scipy."""
    # Set end date to today if not provided
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    # Validate method
    if method not in ["grid", "scipy"]:
        print("❌ Error: method must be 'grid' or 'scipy'")
        raise typer.Exit(1)

    # Create optimizer
    optimizer = WeightOptimizer(
        start_date=start,
        end_date=end,
        max_drawdown_threshold=max_dd,
        top_n=top_n,
        band=band,
    )

    try:
        print(f"🚀 Starting {method} optimization...")

        if method == "grid":
            results = optimizer.grid_search(weight_step=step, verbose=True)
        else:  # scipy
            results = optimizer.scipy_optimize(verbose=True)

        # Save results if requested
        if save_results and results.get("all_results") is not None:
            filename = f"weight_optimization_{method}_{start}_{end}.csv"
            save_optimization_results(results, filename)

    except Exception as e:
        print(f"❌ Optimization failed: {e}")
        raise typer.Exit(1)


def run_compare_weights(
    weights: list,
    start: str,
    end: str | None,
    max_dd: float,
    top_n: int,
    band: int,
    include_common: bool,
    save_results: bool,
):
    """Compare specific weight combinations."""
    # Set end date to today if not provided
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    # Parse weight combinations
    weight_combinations = []

    try:
        for weight_str in weights:
            parsed_weights = parse_weights_string(weight_str)
            weight_combinations.append(parsed_weights)
    except ValueError as e:
        print(f"❌ Error parsing weights: {e}")
        print("💡 Example format: '0.8,0.1,0.1' (must sum to 1.0)")
        raise typer.Exit(1)

    # Add common test combinations if requested
    if include_common:
        common_combinations = generate_test_combinations()
        # Remove duplicates
        for combo in common_combinations:
            if combo not in weight_combinations:
                weight_combinations.append(combo)

    # Create optimizer
    optimizer = WeightOptimizer(
        start_date=start,
        end_date=end,
        max_drawdown_threshold=max_dd,
        top_n=top_n,
        band=band,
    )

    try:
        results_df = optimizer.compare_combinations(weight_combinations)

        # Save results if requested
        if save_results and not results_df.empty:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"weight_comparison_{start}_{end}_{timestamp}.csv"

            filepath = os.path.join("output", filename)
            # Convert to records for storage
            records = results_df.to_dict("records")
            if save_to_file(records, filepath):
                print(f"📁 Results saved to: {filepath}")
            else:
                print("⚠️ Caching is disabled - results were not saved to disk")
            print(f"📁 Results saved to: {filepath}")

    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        raise typer.Exit(1)
