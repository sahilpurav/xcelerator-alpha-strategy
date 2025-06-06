"""
Optimization module for backtesting strategies.

This module provides tools for optimizing strategy parameters,
particularly for weight optimization in momentum strategies.
"""

from .weight_optimizer import WeightOptimizer
from .engines import WeightedBacktestEngine
from . import utils

__all__ = ['WeightOptimizer', 'WeightedBacktestEngine', 'utils']
