import requests
import os
import json
from utils.date import get_last_trading_day

def _fetch_red_flags(measure: str, cache_dir: str ="cache/filters") -> list:
    """
    Fetches red flag data (ASM or GSM) from the NSE website and caches it.
    Args:
        measure (str): Type of red flag data to fetch ("asm" or "gsm").
        cache_dir (str): Directory to cache the fetched data.
    Returns:
        list: Parsed JSON data from the response, or None if an error occurs.
    """
    if measure not in ["asm", "gsm"]:
        raise ValueError("Invalid measure type. Use 'asm' or 'gsm'.")

    last_trading_date = get_last_trading_day()
    output_file = f"{cache_dir}/{measure}-{last_trading_date}.json"

    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            return json.load(f)

    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://www.nseindia.com/reports/{measure.lower()}",
        "Accept": "application/json",
    }

    try:
        session.get(f"https://www.nseindia.com/reports/{measure.lower()}", headers=headers, timeout=10)
        response = session.get(f"https://www.nseindia.com/api/report{measure.upper()}?json=true", headers=headers, timeout=10)

        if response.status_code == 200:
            os.makedirs(cache_dir, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(response.json(), f, indent=2)
            
            return response.json()
        else:
            print("Failed status:", response.status_code)
            print("Text:", response.text)
            return None

    except Exception as e:
        print("Exception occurred:", e)
        return None

def get_excluded_asm_symbols() -> set:
    """
    Extracts symbols from ASM data that are to be excluded.
    Here we will exclude all symbols that are flags as LT-ASM or ST-ASM Stage II.
    ST-ASM Stage I is not excluded as they are still strong from momentum perspective.
    """
    asm_data = _fetch_red_flags("asm")
    lt = {entry["symbol"] for entry in asm_data.get("longterm", {}).get("data", [])}
    st = {
        entry["symbol"]
        for entry in asm_data.get("shortterm", {}).get("data", [])
        if entry.get("asmSurvIndicator", "").strip() == "Stage II"
    }
    return lt | st

def get_excluded_gsm_symbols() -> set:
    """
    Extracts symbols from GSM data that are to be excluded.
    """
    gsm_data = _fetch_red_flags("gsm")
    return {item["symbol"].strip() for item in gsm_data if "symbol" in item}