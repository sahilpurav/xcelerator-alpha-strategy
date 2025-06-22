"""
Utility functions for optimization module.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict


def validate_weights(weights: Tuple[float, float, float]) -> bool:
    """
    Validate that weights are valid (sum to 1.0, all non-negative).
    
    Args:
        weights: Tuple of (return_weight, rsi_weight, proximity_weight)
        
    Returns:
        True if weights are valid, False otherwise
    """
    if len(weights) != 3:
        return False
    
    # Check if all weights are non-negative
    if any(w < 0 for w in weights):
        return False
    
    # Check if weights sum to approximately 1.0 (allow small floating point errors)
    if not np.isclose(sum(weights), 1.0, atol=1e-6):
        return False
    
    return True


def parse_weights_string(weights_str: str) -> Tuple[float, float, float]:
    """
    Parse a comma-separated string of weights.
    
    Args:
        weights_str: String like "0.8,0.1,0.1" or "0.6, 0.2, 0.2"
        
    Returns:
        Tuple of parsed weights
        
    Raises:
        ValueError: If string cannot be parsed or weights are invalid
    """
    try:
        # Remove any whitespace and split by comma
        parts = [part.strip() for part in weights_str.split(',')]
        
        if len(parts) != 3:
            raise ValueError(f"Expected 3 weights, got {len(parts)}")
        
        # Convert to floats
        weights = tuple(float(part) for part in parts)
        
        # Validate
        if not validate_weights(weights):
            raise ValueError(f"Invalid weights: {weights}. Must be non-negative and sum to 1.0")
        
        return weights
        
    except Exception as e:
        raise ValueError(f"Could not parse weights '{weights_str}': {e}")


def format_weights_for_display(weights: Tuple[float, float, float]) -> str:
    """
    Format weights tuple for display.
    
    Args:
        weights: Tuple of (return_weight, rsi_weight, proximity_weight)
        
    Returns:
        Formatted string like "(0.8, 0.1, 0.1)"
    """
    return f"({weights[0]:.1f}, {weights[1]:.1f}, {weights[2]:.1f})"


def generate_test_combinations() -> List[Tuple[float, float, float]]:
    """
    Generate a set of common test weight combinations for quick comparison.
    
    Returns:
        List of weight tuples for testing
    """
    return [
        (0.8, 0.1, 0.1),   # Current strategy (return-heavy)
        (0.7, 0.2, 0.1),   # Slightly more RSI
        (0.6, 0.3, 0.1),   # More RSI emphasis  
        (0.6, 0.2, 0.2),   # Balanced RSI and proximity
        (0.5, 0.4, 0.1),   # RSI-heavy
        (0.5, 0.3, 0.2),   # Balanced approach
        (0.4, 0.4, 0.2),   # Equal return/RSI
        (0.33, 0.33, 0.34), # Equal weights
        (0.3, 0.5, 0.2),   # RSI-dominant
        (0.2, 0.6, 0.2),   # Very RSI-heavy
        (0.9, 0.05, 0.05), # Very return-heavy
        (0.5, 0.25, 0.25), # Equal RSI and proximity
    ]


def save_optimization_results(results: Dict, filename: str = None) -> str:
    """
    Save optimization results to a CSV file.
    
    Args:
        results: Results dictionary from optimization
        filename: Optional filename (auto-generated if not provided)
        
    Returns:
        Path to saved file
    """
    import os
    from datetime import datetime
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"optimization_results_{timestamp}.csv"
    
    # Ensure output directory exists
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filepath = os.path.join(output_dir, filename)
    
    # Save results DataFrame if available
    if 'all_results' in results and results['all_results'] is not None:
        results['all_results'].to_csv(filepath, index=False)
        print(f"📁 Results saved to: {filepath}")
    else:
        print("⚠️ No results DataFrame to save")
    
    return filepath


def load_optimization_results(filepath: str) -> pd.DataFrame:
    """
    Load optimization results from a CSV file.
    
    Args:
        filepath: Path to the results CSV file
        
    Returns:
        DataFrame with optimization results
    """
    return pd.read_csv(filepath)


def get_top_n_results(results_df: pd.DataFrame, n: int = 10, 
                     constraint_column: str = 'meets_constraint',
                     sort_column: str = 'cagr') -> pd.DataFrame:
    """
    Get top N results that meet constraints.
    
    Args:
        results_df: Results DataFrame
        n: Number of top results to return
        constraint_column: Column name for constraint satisfaction
        sort_column: Column to sort by (descending)
        
    Returns:
        DataFrame with top N results
    """
    # Filter to only valid results
    valid_results = results_df[results_df[constraint_column] == True]
    
    if valid_results.empty:
        print("⚠️ No results meet the constraint!")
        return pd.DataFrame()
    
    # Sort by the specified column (descending) and return top N
    return valid_results.sort_values(sort_column, ascending=False).head(n)


def analyze_weight_patterns(results_df: pd.DataFrame) -> Dict:
    """
    Analyze patterns in successful weight combinations.
    
    Args:
        results_df: Results DataFrame
        
    Returns:
        Dictionary with pattern analysis
    """
    valid_results = results_df[results_df['meets_constraint'] == True]
    
    if valid_results.empty:
        return {"message": "No valid results to analyze"}
    
    analysis = {
        "total_valid": len(valid_results),
        "weight_stats": {
            "return_weight": {
                "mean": valid_results['return_weight'].mean(),
                "std": valid_results['return_weight'].std(),
                "min": valid_results['return_weight'].min(),
                "max": valid_results['return_weight'].max()
            },
            "rsi_weight": {
                "mean": valid_results['rsi_weight'].mean(), 
                "std": valid_results['rsi_weight'].std(),
                "min": valid_results['rsi_weight'].min(),
                "max": valid_results['rsi_weight'].max()
            },
            "proximity_weight": {
                "mean": valid_results['proximity_weight'].mean(),
                "std": valid_results['proximity_weight'].std(), 
                "min": valid_results['proximity_weight'].min(),
                "max": valid_results['proximity_weight'].max()
            }
        },
        "performance_stats": {
            "cagr": {
                "mean": valid_results['cagr'].mean(),
                "std": valid_results['cagr'].std(),
                "best": valid_results['cagr'].max()
            },
            "max_drawdown": {
                "mean": valid_results['max_drawdown'].mean(),
                "std": valid_results['max_drawdown'].std(),
                "best": valid_results['max_drawdown'].max()  # Highest (least negative)
            }
        }
    }
    
    return analysis
