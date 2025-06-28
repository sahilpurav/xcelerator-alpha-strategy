"""
Optimization module for backtesting strategies.

This module provides tools for optimizing strategy parameters,
particularly for weight optimization in momentum strategies.
"""

from . import utils
from .engines import WeightedBacktestEngine
from .weight_optimizer import WeightOptimizer

__all__ = ["WeightOptimizer", "WeightedBacktestEngine", "utils"]
