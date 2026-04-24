import pandas as pd
import json
import re

# ─────────────────────────────────────────────
# STEP 1 — Load original CSV
# ─────────────────────────────────────────────
df = pd.read_csv("fit_watches_flipkart_large.csv", encoding="utf-8-sig")
df["brand"] = df["Brand"].fillna("Unknown").astype(str).str.strip()

# Clean prices
df["Price_Clean"] = pd.to_numeric(
    df["Current Price"].astype(str).str.replace(r"[₹,\s]", "", regex=True),
    errors="coerce"
)
df["OriginalPrice_Clean"] = pd.to_numeric(
    df["Original Price"].astype(str).str.replace(r"[₹,\s]", "", regex=True),
    errors="coerce"
)
df["Discount_Numeric"] = df["Discount %"].astype(str).str.extract(r"(\d+)")[0].astype(float)
df["Savings"] = df["OriginalPrice_Clean"] - df["Price_Clean"]
df["Discount_Calculated"] = ((df["Savings"] / df["OriginalPrice_Clean"]) * 100).round(1)
df["Discount_Suspicious"] = abs(df["Discount_Numeric"] - df["Discount_Calculated"]) > 15

print(f"✅ Loaded original CSV: {df.shape[0]} rows")

# ─────────────────────────────────────────────
# STEP 2 — Local feature inference
# ─────────────────────────────────────────────
def contains(text, *keywords):
    t = str(text).lower()
    return any(k.lower() in t for k in keywords)

def infer_features(row):
    name     = str(row.get("Name", ""))
    health   = str(row.get("Health Features", ""))
    smart    = str(row.get("Smart Functions", ""))
    display  = str(row.get("Display Type", ""))
    combined = f"{name} {health} {smart}".lower()

    has_spo2             = contains(combined, "spo2", "blood oxygen")
    has_sleep_tracker    = contains(combined, "sleep")
    has_stress_monitor   = contains(combined, "stress")
    has_gps              = contains(combined, "gps")
    has_bt_calling       = contains(combined, "bt calling", "bluetooth calling", "bt call")
    has_voice_assistant  = contains(combined, "voice assistant", "ai voice")
    has_women_health     = contains(combined, "women", "menstrual", "female")
    has_water_resistance = contains(combined, "waterproof", "water resist", "ip67", "ip68")
    has_music_control    = contains(combined, "music")
    has_notifications    = contains(combined, "notification", "alert", "message")
    has_aod              = contains(combined, "aod", "always on display")

    match = re.search(r'(\d+)\+?\s*sports?\s*mode', combined)
    sports_modes = int(match.group(1)) if match else None

    d = display.upper()
    if "AMOLED" in d:           display_quality = "AMOLED"
    elif "SUPER HD" in combined: display_quality = "Super HD"
    elif "FULL HD" in combined:  display_quality = "Full HD"
    elif "HD" in combined:       display_quality = "HD"
    else:                        display_quality = "Basic"

    feature_count = sum([
        has_spo2, has_sleep_tracker, has_stress_monitor,
        has_gps, has_bt_calling, has_voice_assistant,
        has_women_health, has_water_resistance,
        has_music_control, has_notifications
    ])
    price = row.get("Price_Clean", 0) or 0

    if price >= 3000 and feature_count >= 7:   segment = "Premium Smart"
    elif has_bt_calling and feature_count >= 5: segment = "Smart"
    elif feature_count >= 3:                    segment = "Fitness-Focused"
    else:                                       segment = "Basic"

    return {
        "has_spo2":              has_spo2,
        "has_sleep_tracker":     has_sleep_tracker,
        "has_stress_monitor":    has_stress_monitor,
        "has_gps":               has_gps,
        "has_bluetooth_calling": has_bt_calling,
        "has_voice_assistant":   has_voice_assistant,
        "has_women_health":      has_women_health,
        "has_water_resistance":  has_water_resistance,
        "has_music_control":     has_music_control,
        "has_notifications":     has_notifications,
        "has_aod":               has_aod,
        "sports_modes_count":    sports_modes,
        "display_quality":       display_quality,
        "inferred_segment":      segment,
        "feature_count":         feature_count,
    }

local_features = df.apply(infer_features, axis=1, result_type="expand")
df = pd.concat([df, local_features], axis=1)
print(f"✅ Local features inferred for all {len(df)} rows")

# ─────────────────────────────────────────────
# STEP 3 — Merge brand_cache.json
# ─────────────────────────────────────────────
with open("brand_cache.json", "r") as f:
    brand_info_map = json.load(f)

brand_fields = [
    "parent_company", "country_of_origin", "founded_year",
    "brand_tier", "primary_target_audience",
    "number_of_associated_brands", "is_direct_to_consumer"
]
for field in brand_fields:
    df[field] = df["brand"].map(lambda b: brand_info_map.get(b, {}).get(field, "N/A"))

print(f"✅ Brand info merged for {df['country_of_origin'].ne('N/A').sum()} rows")

# ─────────────────────────────────────────────
# STEP 4 — Merge enriched_rows_cache.csv (20 API scores)
# ─────────────────────────────────────────────
scores_partial = pd.read_csv("enriched_rows_cache.csv")

# These columns are what we need from the partial scores
score_cols = ["value_for_money_score", "feature_richness_score"]

# Initialize as NaN first
df["value_for_money_score"] = None
df["feature_richness_score"] = None

# Assign by row index (scores were generated in same order as df)
n = len(scores_partial)
df.loc[:n-1, "value_for_money_score"] = scores_partial["value_for_money_score"].values
df.loc[:n-1, "feature_richness_score"] = scores_partial["feature_richness_score"].values

print(f"✅ API scores merged for first {n} rows")

# ─────────────────────────────────────────────
# STEP 5 — Derive scores for remaining 150 rows
# ─────────────────────────────────────────────
# value_for_money: more features per rupee = higher score
df["value_for_money_score"] = df["value_for_money_score"].fillna(
    ((df["feature_count"] / df["Price_Clean"].clip(lower=1)) * 1000)
    .clip(1, 10).round(1)
)

# feature_richness: out of 10 possible boolean features
df["feature_richness_score"] = df["feature_richness_score"].fillna(
    df["feature_count"].clip(1, 10).astype(float)
)

print(f"✅ Derived scores filled for remaining {len(df) - n} rows")

# ─────────────────────────────────────────────
# STEP 6 — Final save
# ─────────────────────────────────────────────
df.to_csv("enhanced_fitness_watches_data.csv", index=False, encoding="utf-8-sig")
print(f"\n✅ DONE! Saved: enhanced_fitness_watches_data.csv")
print(f"   Shape: {df.shape[0]} rows × {df.shape[1]} columns")

print("\n📊 Columns in final file:")
print(list(df.columns))

print("\n📈 Segment Distribution:")
print(df["inferred_segment"].value_counts())

print("\n🌍 Country Distribution:")
print(df["country_of_origin"].value_counts())

print("\n💰 Score Preview:")
print(df[["brand", "Price_Clean", "feature_count",
          "value_for_money_score", "feature_richness_score"]].head(10).to_string(index=False))