from typing import List
from data.surveillance import get_excluded_asm_symbols, get_excluded_gsm_symbols, get_excluded_esm_symbols
import time

def apply_universe_filters(symbols: List[str]) -> List[str]:
    """
    Applies universe filters to the given list of symbols.
    Filters out symbols based on ASM, GSM and ESM data.

    We've added 1 second of delay while fetching the next flags to avoid hitting
    the NSE API too frequently.
    """
    asm = get_excluded_asm_symbols()
    time.sleep(1)
    gsm = get_excluded_gsm_symbols()
    time.sleep(1)
    esm = get_excluded_esm_symbols()
    excluded = set().union(asm, gsm, esm)

    return [s for s in symbols if s not in excluded]