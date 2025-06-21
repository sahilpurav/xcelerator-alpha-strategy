import os
import json
import requests
from utils.market import get_last_trading_day

# MarketSmith India API endpoints
ASM_LONGTERM_URL = "https://marketsmithindia.com/gateway/simple-api/ms-india/lists/getASMList.json?type=1&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+250605180633+-2034648918"
ASM_SHORTTERM_URL = "https://marketsmithindia.com/gateway/simple-api/ms-india/lists/getASMList.json?type=0&ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+250605180633+-2034648918"
GSM_URL = "https://marketsmithindia.com/gateway/simple-api/ms-india/lists/getGSMList.json?ms-auth=3990+MarketSmithINDUID-Web0000000000+MarketSmithINDUID-Web0000000000+0+250605180633+-2034648918"

def fetch_api(url: str, key: str) -> list:
    """
    Fetches data from the MarketSmith India API.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        ),
        "Referer": "https://marketsmithindia.com/",
        "Accept": "application/json",
        "Origin": "https://marketsmithindia.com",
    }

    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()["response"]["results"][key]

def save_json(data: object, filename: str, cache_dir: str):
    os.makedirs(cache_dir, exist_ok=True)
    filepath = os.path.join(cache_dir, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved: {filepath}")

def scrape(measure: str, cache_dir: str):
    """
    Unified scrape interface consistent with NSE scraper.
    Accepts 'asm' or 'gsm' and saves file in the specified cache directory.
    """
    measure = measure.lower()
    assert measure in {"asm", "gsm"}, "Measure must be either 'asm' or 'gsm'"

    date_str = get_last_trading_day()

    if measure == "asm":
        longterm_raw = fetch_api(ASM_LONGTERM_URL, "nseasmlist")
        shortterm_raw = fetch_api(ASM_SHORTTERM_URL, "nseasmlist")

        longterm = [{"symbol": e["symbol"], "asmSurvIndicator": e["asmStage"]} for e in longterm_raw]
        shortterm = [{"symbol": e["symbol"], "asmSurvIndicator": e["asmStage"]} for e in shortterm_raw]

        output = {
            "longterm": {"data": longterm},
            "shortterm": {"data": shortterm}
        }
        save_json(output, f"asm-{date_str}.json", cache_dir)

    elif measure == "gsm":
        gsm_raw = fetch_api(GSM_URL, "nsegsmlist")
        output = [{"symbol": e["symbol"]} for e in gsm_raw]
        save_json(output, f"gsm-{date_str}.json", cache_dir)
