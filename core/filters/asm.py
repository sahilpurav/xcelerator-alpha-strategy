import undetected_chromedriver as uc
import json
import time
import os

def fetch_asm_from_api_page():
    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options)
    print("✅ Browser launched")

    # Step 1: Go to ASM reports page to pass Cloudflare check
    print("🌐 Opening ASM reports page...")
    driver.get("https://www.nseindia.com/reports/asm")
    time.sleep(6)

    # Step 2: Visit ASM API URL (JSON shown in browser <pre>)
    print("📡 Fetching JSON directly via browser...")
    driver.get("https://www.nseindia.com/api/reportASM?json=true")
    time.sleep(3)

    # Step 3: Grab the <pre> content
    body = driver.find_element("tag name", "pre").text
    driver.quit()

    # Step 4: Parse and save
    asm_data = json.loads(body)

    # Step 4: Save to file
    os.makedirs("cache", exist_ok=True)
    with open("cache/asm.json", "w") as f:
        json.dump(asm_data, f, indent=2)

    print("✅ ASM data saved to cache/asm.json")