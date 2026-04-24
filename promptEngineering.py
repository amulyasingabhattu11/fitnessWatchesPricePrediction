from google import genai
from google.genai import types
from dotenv import load_dotenv
import pandas as pd
import json
import time
import re
import os

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
load_dotenv()
os.environ.pop("GOOGLE_API_KEY", None)
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash-lite"

BRAND_CACHE_FILE = "brand_cache.json"

# ─────────────────────────────────────────────
# STEP 1 — Load Dataset
# ─────────────────────────────────────────────
df = pd.read_csv("fit_watches_flipkart_large.csv", encoding="utf-8-sig")
df["brand"] = df["Brand"].fillna("Unknown").astype(str).str.strip()

unique_brands = df["brand"].unique()
print(f"✅ Loaded: {df.shape[0]} rows | {len(unique_brands)} unique brands")

# ─────────────────────────────────────────────
# STEP 2 — Brand Info Query (1 API call per unique brand only)
# ─────────────────────────────────────────────
def get_brand_info(brand_name: str) -> dict:
    prompt = f"""You are an expert in the fitness watch industry.

Given the brand name: "{brand_name}"

Return ONLY a valid raw JSON object with exactly these keys:
{{
  "parent_company": "string",
  "number_of_associated_brands": integer
}}

Rules:
- Return raw JSON only. No markdown. No explanation.
- If the brand is independent, set parent_company to the brand name itself.
- number_of_associated_brands: how many sub-brands or sibling brands the parent company owns.
- If unknown, use "Unknown" for strings and 0 for integers.

Brand: "{brand_name}"
"""
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            raw = re.sub(r"```json|```", "", response.text.strip()).strip()
            return json.loads(raw)
        except Exception as e:
            err = str(e)
            if "429" in err:
                wait = 60 * (attempt + 1)
                print(f"   ⏳ Rate limit. Waiting {wait}s...")
                time.sleep(wait)
            elif "503" in err:
                wait = 30 * (attempt + 1)
                print(f"   ⏳ Overloaded. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"   ⚠️ Error for '{brand_name}': {e}")
                return {}
    return {}

# ─────────────────────────────────────────────
# STEP 3 — Enrich with Cache
# ─────────────────────────────────────────────
if os.path.exists(BRAND_CACHE_FILE):
    with open(BRAND_CACHE_FILE, "r") as f:
        brand_info_map = json.load(f)
    brand_info_map = {k: v for k, v in brand_info_map.items() if v}
    print(f"✅ Cache loaded: {len(brand_info_map)}/{len(unique_brands)} already done\n")
else:
    brand_info_map = {}
    print("📭 No cache found. Starting fresh.\n")

for i, brand in enumerate(unique_brands, 1):
    if brand in brand_info_map:
        print(f"[{i}/{len(unique_brands)}] Skipping '{brand}' (cached ✓)")
        continue

    print(f"[{i}/{len(unique_brands)}] Fetching: {brand}...", end=" ", flush=True)
    info = get_brand_info(brand)

    if info:
        brand_info_map[brand] = info
        with open(BRAND_CACHE_FILE, "w") as f:
            json.dump(brand_info_map, f, indent=2)
        print(f"→ parent: {info.get('parent_company','?')} | associated: {info.get('number_of_associated_brands','?')}")
    else:
        print("→ ❌ Failed, will retry next run")

    time.sleep(5)  # gentle delay between calls

# ─────────────────────────────────────────────
# STEP 4 — Map to DataFrame & Save
# ─────────────────────────────────────────────
df["parent_company"]             = df["brand"].map(lambda b: brand_info_map.get(b, {}).get("parent_company", "N/A"))
df["number_of_associated_brands"]= df["brand"].map(lambda b: brand_info_map.get(b, {}).get("number_of_associated_brands", "N/A"))

df.to_csv("enhanced_fitness_watches_data.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ Saved: {df.shape[0]} rows × {df.shape[1]} columns")

print("\n📊 Brand Summary:")
print(df[["brand", "parent_company", "number_of_associated_brands"]]
      .drop_duplicates("brand")
      .to_string(index=False))