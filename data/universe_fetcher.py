import os
from datetime import datetime
from io import StringIO

import pandas as pd
import requests

from utils.cache import is_caching_enabled, load_from_file, save_to_file


def get_benchmark_symbol(universe: str = "nifty500") -> str:
    """
    Get the benchmark symbol based on the universe.

    Args:
        universe (str): Universe name (e.g., "nifty500", "nifty100")

    Returns:
        str: Yahoo Finance benchmark symbol
    """
    universe_to_symbol = {
        "nifty500": "NIFTY 500",
        "nifty100": "NIFTY 100",
    }

    if universe not in universe_to_symbol:
        raise ValueError(
            f"Unsupported universe: {universe}. Supported universes: {list(universe_to_symbol.keys())}"
        )

    return universe_to_symbol[universe]


def get_universe_symbols(
    universe: str = "nifty500", cache_dir: str = "cache/universe"
) -> list[str]:
    """
    Fetch and cache stock symbols from NSE for a given universe.

    Args:
        universe (str): e.g., "nifty50", "nifty100", "nifty500"
        cache_dir (str): Directory to store the cached file

    Returns:
        Tuple[List[str], List[str]]: raw NSE symbols, Yahoo-formatted symbols
    """

    try:
        size = int(universe.replace("nifty", ""))
    except ValueError:
        raise ValueError("Universe format should be like 'nifty100', 'nifty500' etc.")

    url = f"https://www.niftyindices.com/IndexConstituent/ind_nifty{size}list.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    today = datetime.today().strftime("%Y-%m-%d")
    cache_file = os.path.join(cache_dir, f"{universe}-{today}.csv")

    # Try to load from cache
    if is_caching_enabled():
        cached_data = load_from_file(cache_file)
        if cached_data is not None:
            df = pd.DataFrame(cached_data)
        else:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch data from {url}")
            df = pd.read_csv(StringIO(response.text))

            # Convert to list of dicts for storage
            records = df.to_dict("records")
            save_to_file(records, cache_file)
    else:
        # Bypass cache if disabled
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}")
        df = pd.read_csv(StringIO(response.text))

    # We need to extract the Symbol when series is EQ
    symbols = df[df["Series"] == "EQ"]["Symbol"].dropna().unique().tolist()

    # Exclude symbols starting with "DUMMY" and return the rest
    return [s for s in symbols if not s.startswith("DUMMY")]
