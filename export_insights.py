import pandas as pd
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def load_export_file(filepath):
    """Load export data from Excel file"""
    df = pd.read_excel(filepath, sheet_name=0, skiprows=2)
    # Rename columns properly
    df.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_Current_Million',
                  'Share_Current', 'Value_Next_Million', 'Share_Next', 'Growth_%']
    df = df.dropna(subset=['Commodity', 'Value_Current_Million'])
    return df

# Load files with year detection
files = {
    2020: "/Users/umashankar/Downloads/import export data/TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
    2022: "/Users/umashankar/Downloads/import export data/TradeStat-Eidb-Export-Commodity-wise2022.xlsx",
    2023: "/Users/umashankar/Downloads/import export data/TradeStat-Eidb-Export-Commodity-wise.xlsx",
}

# Load data
data = {}
for year, filepath in files.items():
    if os.path.exists(filepath):
        try:
            df = load_export_file(filepath)
            # Parse numeric columns
            df['Value_Current_Million'] = pd.to_numeric(df['Value_Current_Million'], errors='coerce')
            df['Growth_%'] = pd.to_numeric(df['Growth_%'], errors='coerce')
            df['Year'] = year
            data[year] = df
            print(f"✓ Loaded {year}: {len(df)} commodities")
        except Exception as e:
            print(f"✗ Error loading {year}: {e}")

if not data:
    print("No data loaded!")
    exit(1)

# ===== ANALYSIS 1: High Value per Unit (proxy: high growth + high value) =====
print("\n" + "="*90)
print("HIGH-VALUE EXPORTS WITH STRONG GROWTH (Last Available Year)")
print("="*90)

latest_year = max(data.keys())
latest_df = data[latest_year].copy()

# Filter: Value > $1M and growth > 20% (strong performers)
high_value_growth = latest_df[
    (latest_df['Value_Current_Million'] > 1) &
    (latest_df['Growth_%'] > 20)
].sort_values('Value_Current_Million', ascending=False)

if len(high_value_growth) > 0:
    print(f"\nTop 20 exports: Value >$1M + Growth >20% (Year {latest_year}):")
    display = high_value_growth[['Commodity', 'Value_Current_Million', 'Growth_%']].head(20)
    print(display.to_string(index=False))
else:
    print("No exports found with Value >$1M and Growth >20%")

# ===== ANALYSIS 2: 5-Year Growth Trend =====
print("\n" + "="*90)
print("5-YEAR GROWTH TREND ANALYSIS (2020 → 2023)")
print("="*90)

if 2020 in data and 2023 in data:
    df_2020 = data[2020][['Commodity', 'Value_Current_Million']].rename(
        columns={'Value_Current_Million': 'Value_2020'})
    df_2023 = data[2023][['Commodity', 'Value_Current_Million']].rename(
        columns={'Value_Current_Million': 'Value_2023'})

    # Merge on commodity
    merged = pd.merge(df_2020, df_2023, on='Commodity', how='inner')
    merged['Value_2020'] = pd.to_numeric(merged['Value_2020'], errors='coerce')
    merged['Value_2023'] = pd.to_numeric(merged['Value_2023'], errors='coerce')
    merged = merged.dropna()

    # Calculate growth
    merged['Growth_5yr_%'] = ((merged['Value_2023'] - merged['Value_2020']) /
                             merged['Value_2020'] * 100)
    merged['Absolute_Growth_M'] = merged['Value_2023'] - merged['Value_2020']

    # High-value exports that grew
    high_value_5yr = merged[
        (merged['Value_2023'] > 50) &  # At least $50M in 2023
        (merged['Growth_5yr_%'] > 10)    # 10%+ growth over 5 years
    ].sort_values('Value_2023', ascending=False)

    print(f"\nExports: Value $50M+ in 2023 + 10%+ Growth (2020-2023):")
    print(f"Found {len(high_value_5yr)} commodities\n")
    display_5yr = high_value_5yr[['Commodity', 'Value_2020', 'Value_2023',
                                   'Growth_5yr_%', 'Absolute_Growth_M']].head(25)
    print(display_5yr.to_string(index=False))

    # Emerging categories (lower base but strong growth)
    print("\n" + "-"*90)
    print("EMERGING HIGH-GROWTH EXPORTS ($10-50M in 2023, 50%+ Growth 2020-2023):")
    emerging = merged[
        (merged['Value_2023'] > 10) &
        (merged['Value_2023'] <= 50) &
        (merged['Growth_5yr_%'] > 50)
    ].sort_values('Growth_5yr_%', ascending=False)
    print(f"Found {len(emerging)} commodities\n")
    display_emerging = emerging[['Commodity', 'Value_2020', 'Value_2023', 'Growth_5yr_%']].head(15)
    print(display_emerging.to_string(index=False))

# ===== ANALYSIS 3: Premium/Specialty Products (High unit value proxy) =====
print("\n" + "="*90)
print("PREMIUM EXPORTS (Likely high value-per-unit)")
print("="*90)

# High value exports with low-growth (stable, premium) + growing (best case)
premium_candidates = latest_df[latest_df['Value_Current_Million'] > 500].sort_values(
    'Value_Current_Million', ascending=False)

print(f"\nTop premium exports ($500M+ value in {latest_year}):")
display_premium = premium_candidates[['Commodity', 'Value_Current_Million', 'Growth_%']].head(15)
print(display_premium.to_string(index=False))

# ===== Summary Stats =====
print("\n" + "="*90)
print("SUMMARY STATISTICS")
print("="*90)

for year in sorted(data.keys()):
    df = data[year]
    total_value = df['Value_Current_Million'].sum()
    print(f"\n{year}:")
    print(f"  Total exports: ${total_value:,.0f}M")
    print(f"  Commodities: {len(df)}")
    print(f"  Avg value/commodity: ${df['Value_Current_Million'].mean():,.1f}M")
    print(f"  Median value/commodity: ${df['Value_Current_Million'].median():,.1f}M")

    # Top 5 commodities
    top5 = df.nlargest(5, 'Value_Current_Million')[['Commodity', 'Value_Current_Million']]
    top5_str = ', '.join([f"{row['Commodity'][:30]}... (${row['Value_Current_Million']:,.0f}M)" for _, row in top5.iterrows()])
    print(f"  Top 5 commodities: {top5_str}")
