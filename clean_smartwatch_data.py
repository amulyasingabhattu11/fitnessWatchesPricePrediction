import pandas as pd
import numpy as np
import re

# Load the dataset
df = pd.read_csv('enhanced_fitness_watches_data.csv', encoding='utf-8-sig')

print(f"Original shape: {df.shape}")

# ─────────────────────────────────────────────
# 1. Clean Price Columns
# ─────────────────────────────────────────────
def clean_price(x):
    if pd.isna(x):
        return np.nan
    return float(str(x).replace('₹', '').replace(',', '').strip())

df['Current Price']   = df['Current Price'].apply(clean_price)
df['Original Price']  = df['Original Price'].apply(clean_price)

# ─────────────────────────────────────────────
# 2. Clean Discount %
# ─────────────────────────────────────────────
def clean_discount(x):
    if pd.isna(x):
        return np.nan
    match = re.search(r'(\d+)', str(x))
    return float(match.group(1)) if match else np.nan

df['Discount %'] = df['Discount %'].apply(clean_discount)

# ─────────────────────────────────────────────
# 3. Validate Discount (flag suspicious ones)
# ─────────────────────────────────────────────
df['Calculated Discount %'] = (
    ((df['Original Price'] - df['Current Price']) / df['Original Price']) * 100
).round(1)

df['Discount Suspicious'] = (
    abs(df['Discount %'] - df['Calculated Discount %']) > 15
)

suspicious_count = df['Discount Suspicious'].sum()
print(f"⚠️  Suspicious discounts: {suspicious_count} rows")

# ─────────────────────────────────────────────
# 4. Clean Display Size (extract numeric inches)
# ─────────────────────────────────────────────
def extract_display_size(x):
    if pd.isna(x):
        return np.nan
    match = re.search(r'(\d+(?:\.\d+)?)', str(x))
    return float(match.group(1)) if match else np.nan

df['Display Size (inches)'] = df['Display Size'].apply(extract_display_size)

# ─────────────────────────────────────────────
# 5. Clean YES/NO Boolean Columns
# ─────────────────────────────────────────────
bool_cols = ['Calorie Count', 'Step Count', 'Heart Rate Monitor']
for col in bool_cols:
    df[col] = df[col].str.strip().str.upper().map({'YES': True, 'NO': False})

# ─────────────────────────────────────────────
# 6. Feature Count from Health Features
# ─────────────────────────────────────────────
def count_features(x):
    if pd.isna(x) or str(x).strip() == '':
        return 0
    return len([f.strip() for f in str(x).split(',') if f.strip()])

df['Health Feature Count'] = df['Health Features'].apply(count_features)
df['Smart Feature Count']  = df['Smart Functions'].apply(count_features)

# ─────────────────────────────────────────────
# 7. Flag Price Anomalies
# (Current Price > Original Price is suspicious)
# ─────────────────────────────────────────────
df['Price Anomaly'] = df['Current Price'] > df['Original Price']
print(f"⚠️  Price anomalies (current > original): {df['Price Anomaly'].sum()} rows")

# ─────────────────────────────────────────────
# 8. Standardize Text Columns
# ─────────────────────────────────────────────
df['Brand']        = df['Brand'].str.strip()
df['Strap Colour'] = df['Strap Colour'].str.strip().str.title()
df['Strap Type']   = df['Strap Type'].str.strip().str.title()
df['Watch Shape']  = df['Watch Shape'].str.strip().str.title()
df['Display Type'] = df['Display Type'].str.strip().str.upper()

# ─────────────────────────────────────────────
# 9. Handle Nulls
# ─────────────────────────────────────────────
df['parent_company'] = df['parent_company'].fillna('Unknown')
df['number_of_associated_brands'] = df['number_of_associated_brands'].fillna(0).astype(int)

# Impute missing Current Price with brand-level median
df['Current Price'] = df.groupby('Brand')['Current Price'].transform(
    lambda x: x.fillna(x.median())
)

# ─────────────────────────────────────────────
# 10. Drop Duplicate Rows
# ─────────────────────────────────────────────
before = len(df)
df = df.drop_duplicates()
print(f"🗑️  Duplicates removed: {before - len(df)}")

# ─────────────────────────────────────────────
# 11. Cast Numeric Columns
# ─────────────────────────────────────────────
numeric_cols = ['Current Price', 'Original Price', 'Discount %',
                'Calculated Discount %', 'Display Size (inches)',
                'Health Feature Count', 'Smart Feature Count',
                'number_of_associated_brands']

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# ─────────────────────────────────────────────
# 12. Save
# ─────────────────────────────────────────────
df.to_csv('cleaned_fitness_watches.csv', index=False, encoding='utf-8-sig')

print(f"\n✅ Cleaned dataset saved.")
print(f"Final shape: {df.shape}")
print("\nData types:")
print(df.dtypes)
print("\nNull counts:")
print(df.isnull().sum()[df.isnull().sum() > 0])