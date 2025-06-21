import os
import json
import time
import undetected_chromedriver as uc
from utils.market import get_last_trading_day

def scrape(measure: str, cache_dir: str = "cache/filters") -> None:
    """
    Scrapes and caches the latest ASM or GSM surveillance list from NSE using a real browser session.

    Args:
        measure (str): Either "asm" or "gsm"
        cache_dir (str): Directory to store the cached JSON file
    """
    measure = measure.lower()
    assert measure in {"asm", "gsm"}, "Measure must be either 'asm' or 'gsm'"

    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options)
    print(f"✅ Browser launched for {measure.upper()} scraping")

    # Step 1: Go to ASM/GSM reports page to pass Cloudflare check
    print(f"🌐 Opening {measure.upper()} reports page...")
    driver.get(f"https://www.nseindia.com/reports/{measure}")
    time.sleep(6)

    # Step 2: Visit ASM/GSM API URL (JSON shown in browser <pre>)
    print("📡 Fetching JSON via browser session...")
    driver.get(f"https://www.nseindia.com/api/report{measure.upper()}?json=true")
    time.sleep(3)

    # Step 3: Grab the <pre> content
    body = driver.find_element("tag name", "pre").text
    driver.quit()

    # Step 4: Parse JSON
    data = json.loads(body)

    # Step 4: Save to file
    os.makedirs(cache_dir, exist_ok=True)
    last_trading_date = get_last_trading_day()
    output_file = f"{cache_dir}/{measure}-{last_trading_date}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"✅ {measure.upper()} data for {last_trading_date} is saved to {output_file}")
