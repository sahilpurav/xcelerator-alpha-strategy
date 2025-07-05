import time

from data.surveillance_fetcher import (
    get_excluded_asm_symbols,
    get_excluded_esm_symbols,
    get_excluded_gsm_symbols,
)


def apply_universe_filters(symbols: list[str]) -> list[str]:
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

    filtered_symbols = [s for s in symbols if s not in excluded]

    # Print simple exclusion summary
    excluded_from_universe = [s for s in symbols if s in excluded]
    if excluded_from_universe:
        excluded_breakdown = []
        if any(s in asm for s in excluded_from_universe):
            asm_count = len([s for s in excluded_from_universe if s in asm])
            excluded_breakdown.append(f"{asm_count} ASM")
        if any(s in gsm for s in excluded_from_universe):
            gsm_count = len([s for s in excluded_from_universe if s in gsm])
            excluded_breakdown.append(f"{gsm_count} GSM")
        if any(s in esm for s in excluded_from_universe):
            esm_count = len([s for s in excluded_from_universe if s in esm])
            excluded_breakdown.append(f"{esm_count} ESM")

        print(
            f"🚫 Excluded {len(excluded_from_universe)} stocks from universe ({', '.join(excluded_breakdown)}): {', '.join(excluded_from_universe)}"
        )

    return filtered_symbols
