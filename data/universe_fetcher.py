import os
import pandas as pd
import requests
from io import StringIO
from typing import Tuple

def get_universe_symbols(universe: str = "nifty500", cache_dir: str = "cache/universe") -> Tuple[list[str]]:
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
    
    url = f"https://archives.nseindia.com/content/indices/ind_nifty{size}list.csv"
    cache_file = os.path.join(cache_dir, f"{universe}.csv")
    os.makedirs(cache_dir, exist_ok=True)

    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
    else:
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch data from {url}")
        df = pd.read_csv(StringIO(response.text))
        df.to_csv(cache_file, index=False)

    symbols = df["Symbol"].dropna().unique().tolist()

    # Exclude symbols starting with "DUMMY" and return the rest
    return [s for s in symbols if not s.startswith("DUMMY")]
