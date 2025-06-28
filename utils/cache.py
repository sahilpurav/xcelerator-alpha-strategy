import csv
import json
import logging
import os
import pickle
from functools import wraps

from config import Config


# Check if caching is enabled via Config
def is_caching_enabled():
    """
    Checks if caching is enabled via the CACHE environment variable.
    Returns True if CACHE=true or is not set, False if CACHE=false.
    """
    return Config.CACHE_ENABLED


# Base file operations that respect the CACHE environment variable
def save_to_file(data, filepath, create_dirs=True):
    """
    Save data to a file if caching is enabled.

    Args:
        data: The data to save
        filepath: Path to save the file
        create_dirs: Whether to create directories if they don't exist

    Returns:
        bool: True if save was successful, False otherwise
    """
    if not is_caching_enabled():
        return False

    if create_dirs:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

    file_ext = os.path.splitext(filepath)[1].lower()

    try:
        if file_ext == ".json":
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        elif file_ext == ".csv":
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                # Handle list of dictionaries
                with open(filepath, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
            else:
                # Simple data
                with open(filepath, "w", newline="") as f:
                    f.write(str(data))
        elif file_ext == ".txt":
            with open(filepath, "w") as f:
                f.write(str(data))
        else:
            # Default to pickle for other types
            with open(filepath, "wb") as f:
                pickle.dump(data, f)
        return True
    except Exception as e:
        logging.error(f"Error saving to {filepath}: {e}")
        return False


def load_from_file(filepath, default=None):
    """
    Load data from a file if it exists and caching is enabled.

    Args:
        filepath: Path to load the file from
        default: Value to return if file doesn't exist or caching is disabled

    Returns:
        The loaded data or default value
    """
    if not is_caching_enabled() or not os.path.exists(filepath):
        return default

    file_ext = os.path.splitext(filepath)[1].lower()

    try:
        if file_ext == ".json":
            with open(filepath, "r") as f:
                return json.load(f)
        elif file_ext == ".csv":
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                return list(reader)
        elif file_ext == ".txt":
            with open(filepath, "r") as f:
                return f.read()
        else:
            # Default to pickle for other types
            with open(filepath, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        logging.error(f"Error loading from {filepath}: {e}")
        return default


# Function decorator for caching results
def cached(cache_path_func):
    """
    Decorator for caching function results

    Args:
        cache_path_func: A function that takes the same args/kwargs as the decorated function
                       and returns the cache file path
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_caching_enabled():
                return func(*args, **kwargs)

            # Get cache path based on function arguments
            cache_path = cache_path_func(*args, **kwargs)

            # Try to load from cache
            result = load_from_file(cache_path)
            if result is not None:
                logging.info(f"Using cached result from {cache_path}")
                return result

            # Calculate result and save to cache
            result = func(*args, **kwargs)
            save_to_file(result, cache_path)
            return result

        return wrapper

    return decorator
