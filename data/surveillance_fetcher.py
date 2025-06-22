import requests
import os
import json
from utils.market import get_last_trading_day
from utils.cache import load_from_file, save_to_file

def _fetch_red_flags(measure: str, cache_dir: str ="cache/filters") -> list:
    """
    Fetches red flag data (ASM or GSM) from the NSE website and caches it.
    Args:
        measure (str): Type of red flag data to fetch ("asm", "gsm" or "esm").
        cache_dir (str): Directory to cache the fetched data.
    Returns:
        list: Parsed JSON data from the response, or None if an error occurs.
    """
    if measure not in ["asm", "gsm", "esm"]:
        raise ValueError("Invalid measure type. Use 'asm', 'gsm' or 'esm'.")

    last_trading_date = get_last_trading_day()
    output_file = f"{cache_dir}/{measure}-{last_trading_date}.json"

    cached_data = load_from_file(output_file)
    if cached_data is not None:
        return cached_data

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
            response_data = response.json()
            save_to_file(response_data, output_file)
            
            return response_data
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
    Only Stage I stocks are allowed from ASM list. All other stages (Stage II, Stage III, Stage IV) 
    from both longterm and shortterm ASM lists will be excluded.
    """
    asm_data = _fetch_red_flags("asm")
    
    # Exclude all longterm ASM stocks that are not Stage I
    lt_excluded = {
        entry["symbol"] 
        for entry in asm_data.get("longterm", {}).get("data", [])
        if entry.get("asmSurvIndicator", "").strip() != "Stage I"
    }
    
    # Exclude all shortterm ASM stocks that are not Stage I
    st_excluded = {
        entry["symbol"]
        for entry in asm_data.get("shortterm", {}).get("data", [])
        if entry.get("asmSurvIndicator", "").strip() != "Stage I"
    }
    
    return lt_excluded | st_excluded

def get_excluded_gsm_symbols() -> set:
    """
    Extracts symbols from GSM data that are to be excluded.
    """
    gsm_data = _fetch_red_flags("gsm")
    return {item["symbol"].strip() for item in gsm_data if "symbol" in item}

def get_excluded_esm_symbols() -> set:
    """
    Extracts symbols from ESM data that are to be excluded.
    """
    gsm_data = _fetch_red_flags("esm")
    return {item["symbol"].strip() for item in gsm_data if "symbol" in item}

def get_asm_exclusion_details(symbols: list[str]) -> dict:
    """
    Returns detailed information about which symbols are excluded from ASM and why.
    
    Args:
        symbols: List of symbols to check
        
    Returns:
        Dictionary with exclusion details including stage information
    """
    asm_data = _fetch_red_flags("asm")
    
    # Build a mapping of symbol to stage info
    symbol_stage_map = {}
    
    # Process longterm ASM data
    for entry in asm_data.get("longterm", {}).get("data", []):
        symbol = entry["symbol"]
        stage = entry.get("asmSurvIndicator", "").strip()
        symbol_stage_map[symbol] = {
            "type": "Longterm ASM",
            "stage": stage,
            "code": entry.get("survCode", ""),
            "description": entry.get("survDesc", "")
        }
    
    # Process shortterm ASM data (may override longterm if symbol exists in both)
    for entry in asm_data.get("shortterm", {}).get("data", []):
        symbol = entry["symbol"]
        stage = entry.get("asmSurvIndicator", "").strip()
        # If symbol exists in both, combine the info
        if symbol in symbol_stage_map:
            symbol_stage_map[symbol]["type"] = "Both LT & ST ASM"
        else:
            symbol_stage_map[symbol] = {
                "type": "Shortterm ASM",
                "stage": stage,
                "code": entry.get("survCode", ""),
                "description": entry.get("survDesc", "")
            }
    
    # Categorize symbols from the input list
    result = {
        "allowed_stage1": [],
        "excluded_non_stage1": [],
        "not_in_asm": []
    }
    
    for symbol in symbols:
        if symbol in symbol_stage_map:
            info = symbol_stage_map[symbol]
            if info["stage"] == "Stage I":
                result["allowed_stage1"].append({
                    "symbol": symbol,
                    "type": info["type"],
                    "stage": info["stage"],
                    "code": info["code"]
                })
            else:
                result["excluded_non_stage1"].append({
                    "symbol": symbol,
                    "type": info["type"],
                    "stage": info["stage"],
                    "code": info["code"],
                    "description": info["description"]
                })
        else:
            result["not_in_asm"].append(symbol)
    
    return result