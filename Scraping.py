import time
import csv
import re
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# =========================
# CHROME SETUP
# =========================
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=chrome_options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

csv_file = "fit_watches_flipkart_large.csv"

# =========================
# CSV INITIALIZATION
# =========================
try:
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Name", "Brand", "Current Price", "Original Price", "Discount %",
            "Strap Colour", "Strap Type", "Watch Shape", "Display Size", "Display Type",
            "Calorie Count", "Step Count", "Heart Rate Monitor", "Health Features", "Smart Functions"
        ])
except PermissionError:
    print(f"❌ Close '{csv_file}' first!")
    driver.quit()
    exit()

def parse_watch_specs(page_text):
    lower_text = page_text.lower()
    
    # PRICE
    prices = re.findall(r'₹[\d,]+', page_text)
    current_price = prices[0] if len(prices) > 0 else "N/A"
    original_price = prices[1] if len(prices) > 1 else current_price
    disc_match = re.search(r'\d+%\s*off', page_text, re.IGNORECASE)
    discount = disc_match.group(0) if disc_match else "0%"

    # STRAP & SHAPE
    strap_type = "Silicone"
    if "metal" in lower_text or "stainless steel" in lower_text: strap_type = "Metal"
    elif "leather" in lower_text: strap_type = "Leather"
    elif "fabric" in lower_text or "nylon" in lower_text: strap_type = "Fabric/Nylon"

    shape = "Square/Rect"
    if "round" in lower_text or "circular" in lower_text: shape = "Round"

    # DISPLAY
    disp_size = re.search(r'(\d+\.?\d*)\s*(inch|inches|mm|cm|\")', lower_text)
    size_val = disp_size.group(0) if disp_size else "N/A"
    panel = "AMOLED" if "amoled" in lower_text else "LCD/TFT"

    # FEATURES YES/NO
    calorie_count = "YES" if any(x in lower_text for x in ["calorie", "kcal", "burn"]) else "NO"
    step_count = "YES" if any(x in lower_text for x in ["step", "pedometer", "walking"]) else "NO"
    heart_rate = "YES" if any(x in lower_text for x in ["heart rate", "hr monitor", "pulse"]) else "NO"

    health = []
    if calorie_count == "YES": health.append("Calorie Count")
    if step_count == "YES": health.append("Step Count")
    if heart_rate == "YES": health.append("Heart Rate")
    if "spo2" in lower_text: health.append("SpO2")
    if "sleep" in lower_text: health.append("Sleep Monitor")
    health_out = ", ".join(health) if health else "Fitness Tracker"

    smart = []
    if "calling" in lower_text or "bt call" in lower_text: smart.append("BT Calling")
    if "voice assistant" in lower_text: smart.append("Voice Assistant")
    smart_out = ", ".join(smart) if smart else "Standard Smart"

    # COLOUR
    colors = ["Black", "Blue", "Pink", "Gold", "Silver", "Grey", "Rose Gold", "Green", "White", "Lavender"]
    found_col = "N/A"
    for c in colors:
        if c.lower() in lower_text:
            found_col = c
            break

    return (current_price, original_price, discount, found_col, strap_type, shape, size_val, panel, 
            calorie_count, step_count, heart_rate, health_out, smart_out)

# =========================
# SCRAPING LOGIC
# =========================
product_count = 0
max_products = 500  # <--- INCREASED THIS VALUE FOR MORE WATCHES

try:
    driver.get("https://www.flipkart.com/search?q=women+fitness+watch")
    time.sleep(5)

    while product_count < max_products:
        print(f"\n--- Scraping Page (Current Total: {product_count}) ---")
        
        # Scroll down multiple times to trigger lazy loading
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        # Collect product links
        items = driver.find_elements(By.XPATH, "//a[contains(@href,'/p/')]")
        all_links = list(set([item.get_attribute("href") for item in items if item.get_attribute("href")]))
        
        print(f"Links found on this page: {len(all_links)}")

        for product_link in all_links:
            if product_count >= max_products:
                break

            try:
                # Open product in new tab
                driver.execute_script("window.open(arguments[0]);", product_link)
                driver.switch_to.window(driver.window_handles[1])
                time.sleep(random.uniform(3, 5))

                page_text = driver.page_source
                
                try:
                    name = driver.find_element(By.TAG_NAME, "h1").text
                except:
                    name = "N/A"
                
                brand = name.split()[0] if name != "N/A" else "N/A"

                # Extract and Save
                specs = parse_watch_specs(page_text)
                
                with open(csv_file, "a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([name, brand] + list(specs))

                product_count += 1
                print(f"Saved {product_count}: {name[:40]}...")

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception as e:
                try:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                continue

        # NEXT PAGE LOGIC
        try:
            # Look for the 'Next' button using a broader XPATH
            next_btn = driver.find_element(By.XPATH, "//a[span[contains(text(), 'Next')]]")
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(5)
        except:
            print("Reached the end of all pages or button not found.")
            break

    print(f"\n✅ DONE! Total Products Scraped: {product_count}")

finally:
    driver.quit()