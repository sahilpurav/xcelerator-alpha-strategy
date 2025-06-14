import os
import json
from typing import List
from data.nse_surveillance import scrape as nse_scrape
from data.msi_surveillance import scrape as msi_scrape
from utils.date import get_last_trading_day

def get_excluded_asm_symbols(asm_data: dict) -> set:
    """
    Extracts symbols from ASM data that are to be excluded.
    Here we will exclude all symbols that are flags as LT-ASM or ST-ASM Stage II.
    ST-ASM Stage I is not excluded as they are still strong from momentum perspective.
    """
    lt = {entry["symbol"] for entry in asm_data.get("longterm", {}).get("data", [])}
    st = {
        entry["symbol"]
        for entry in asm_data.get("shortterm", {}).get("data", [])
        if entry.get("asmSurvIndicator", "").strip() == "Stage II"
    }
    return lt | st

def get_excluded_gsm_symbols(gsm_data: List[dict]) -> set:
    """
    Extracts symbols from GSM data that are to be excluded.
    """
    return {item["symbol"].strip() for item in gsm_data if "symbol" in item}

def apply_universe_filters(symbols: List[str], cache_dir: str = "cache/filters") -> List[str]:
    """
    Applies universe filters to the given list of symbols.
    Filters out symbols based on ASM and GSM data.
    """
    last_trading_date = get_last_trading_day()

    asm_file = os.path.join(cache_dir, f"asm-{last_trading_date}.json")
    gsm_file = os.path.join(cache_dir, f"gsm-{last_trading_date}.json")

    if not os.path.exists(asm_file):
        try:
            msi_scrape("asm", cache_dir)
        except Exception as e:
            nse_scrape("asm", cache_dir)
    
    if not os.path.exists(gsm_file):
        try:
            msi_scrape("gsm", cache_dir)
        except Exception as e:
            nse_scrape("gsm", cache_dir)

    excluded = set()

    if os.path.exists(asm_file):
        with open(asm_file) as f:
            asm_data = json.load(f)
            excluded.update(get_excluded_asm_symbols(asm_data))

    if os.path.exists(gsm_file):
        with open(gsm_file) as f:
            gsm_data = json.load(f)
            excluded.update(get_excluded_gsm_symbols(gsm_data))

    return [s for s in symbols if s not in excluded]