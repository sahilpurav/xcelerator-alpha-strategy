import os
import pandas as pd
import requests
from io import StringIO
from typing import List, Tuple
from core.stock import Stock
import json
from utils.file import File

class Universe:
    CACHE_DIR = "cache/universe"

    @staticmethod
    def _url(size: int) -> str:
        """
        Returns the NSE index CSV URL for given universe size like 100, 200, 500
        """
        return f"https://archives.nseindia.com/content/indices/ind_nifty{size}list.csv"
    
    @staticmethod
    def _get_asm_symbols(filepath="cache/asm.json"):
        try: 
            if File.is_older_than(filepath, 1):
                raise Exception(
                    f"\n ⚠️  ASM file is missing or outdated.\n"
                    f"Please download it manually from:\n"
                    f"https://www.nseindia.com/api/reportASM?json=true\n"
                    f"and save it to: {filepath}"
                )   
            with open(filepath, "r") as f:
                data = json.load(f)

            long_term = [entry["symbol"].strip() + ".NS" for entry in data.get("longterm", {}).get("data", [])]
            short_term = [entry["symbol"].strip() + ".NS" for entry in data.get("shortterm", {}).get("data", [])]

            return set(long_term + short_term)  # or return both separately if needed
        except Exception as e:
            print(f"[ASM Load Error] {e}")
            exit(0)


    @classmethod
    def get_symbols(cls, universe: str, force_refresh: bool = False) -> Tuple[List[str], List[str]]:
        """
        Fetches and caches stock symbols from NSE for the given universe.
        
        Args:
            universe (str): e.g., "nifty500", "nifty100"
            force_refresh (bool): If True, bypass cache and re-download from NSE.

        Returns:
            Tuple[List[str], List[str]]: raw NSE symbols, Yahoo-formatted symbols
        """
        try:
            size = int(universe.replace("nifty", ""))
        except ValueError:
            raise ValueError("Universe format should be like 'nifty100', 'nifty500' etc.")
        
        url = cls._url(size)
        os.makedirs(cls.CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(cls.CACHE_DIR, f"{universe}.csv")

        if not force_refresh and os.path.exists(cache_file):
            df = pd.read_csv(cache_file)
        else:
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch data from {url}")
            df = pd.read_csv(StringIO(response.text))
            df.to_csv(cache_file, index=False)

        raw_symbols = df["Symbol"].tolist()
        yahoo_symbols = [f"{symbol}.NS" for symbol in raw_symbols]

        # Read and deduplicate invalid symbols
        invalid = set()
        if os.path.exists(Stock.INVALID_SYMBOL_FILE):
            with open(Stock.INVALID_SYMBOL_FILE) as f:
                invalid = set(line.strip() for line in f)

        # Exclude stocks which are under ASM
        asm = cls._get_asm_symbols()

        # Combine both sets for exclusion
        excluded_symbols = invalid | asm

        # Filter them out
        raw_symbols = [s for s in raw_symbols if f"{s}.NS" not in excluded_symbols]
        yahoo_symbols = [f"{s}.NS" for s in raw_symbols]

        return raw_symbols, yahoo_symbols