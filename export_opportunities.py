"""
Generate token-optimized exports for Claude API analysis.
Reduces data to essentials: commodity, value, growth rates, and classification.
"""
from __future__ import annotations

import json

import pandas as pd

from trade_common import HEADER_ROWS_TO_SKIP, export_paths, output_dir

# Opportunity classification thresholds (USD million / percent growth 2020->2023)
MEGA_MIN_VALUE_M, MEGA_MIN_GROWTH_PCT = 5000, 50
HIGH_VALUE_MIN_VALUE_M, HIGH_VALUE_MIN_GROWTH_PCT = 1000, 20
EMERGING_MIN_VALUE_M, EMERGING_MIN_GROWTH_PCT = 100, 100
PREMIUM_MIN_VALUE_M = 500
OPPORTUNITY_CATEGORIES = ['MEGA_GROWTH', 'HIGH_VALUE_GROWING', 'EMERGING_OPPORTUNITY']


def classify_opportunity(row):
    """Label a commodity row (needs Value_2023_M and Growth_5yr_%) with its opportunity class."""
    if row['Value_2023_M'] > MEGA_MIN_VALUE_M and row['Growth_5yr_%'] > MEGA_MIN_GROWTH_PCT:
        return 'MEGA_GROWTH'
    elif row['Value_2023_M'] > HIGH_VALUE_MIN_VALUE_M and row['Growth_5yr_%'] > HIGH_VALUE_MIN_GROWTH_PCT:
        return 'HIGH_VALUE_GROWING'
    elif row['Value_2023_M'] > EMERGING_MIN_VALUE_M and row['Growth_5yr_%'] > EMERGING_MIN_GROWTH_PCT:
        return 'EMERGING_OPPORTUNITY'
    elif row['Value_2023_M'] > PREMIUM_MIN_VALUE_M:
        return 'PREMIUM_STABLE'
    else:
        return 'OTHER'


def build_opportunity_frame(df_2020: pd.DataFrame, df_2023: pd.DataFrame) -> pd.DataFrame:
    """Merge the 2020 and 2023 raw sheets (8 positional columns each) and classify every commodity."""
    df_2020.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_2020_M', 'Share', 'Value_Next_M', 'Share_Next', 'Growth_%']
    df_2023.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_2023_M', 'Share', 'Value_Next_M', 'Share_Next', 'Growth_%']

    merged = pd.merge(
        df_2020[['Commodity', 'Value_2020_M', 'HSCode']],
        df_2023[['Commodity', 'Value_2023_M', 'Growth_%']],
        on='Commodity',
        how='inner'
    )

    merged['Value_2020_M'] = pd.to_numeric(merged['Value_2020_M'], errors='coerce')
    merged['Value_2023_M'] = pd.to_numeric(merged['Value_2023_M'], errors='coerce')
    merged['Growth_%'] = pd.to_numeric(merged['Growth_%'], errors='coerce')
    merged = merged.dropna()

    merged['Growth_5yr_%'] = ((merged['Value_2023_M'] - merged['Value_2020_M']) / merged['Value_2020_M'] * 100)
    merged['Opportunity'] = merged.apply(classify_opportunity, axis=1)
    return merged


def create_optimized_export():
    """Create compact CSVs optimized for token reduction"""
    paths = export_paths()
    df_2020 = pd.read_excel(paths[2020], skiprows=HEADER_ROWS_TO_SKIP)
    df_2023 = pd.read_excel(paths[2023], skiprows=HEADER_ROWS_TO_SKIP)
    merged = build_opportunity_frame(df_2020, df_2023)
    out = output_dir()

    # Export 1: High-opportunity commodities only (for Claude analysis)
    high_opp = merged[merged['Opportunity'].isin(OPPORTUNITY_CATEGORIES)].sort_values('Value_2023_M', ascending=False)

    high_opp[['Commodity', 'HSCode', 'Value_2020_M', 'Value_2023_M', 'Growth_5yr_%', 'Opportunity']].to_csv(
        out / 'HIGH_OPPORTUNITY_EXPORTS.csv',
        index=False
    )
    print(f"✓ HIGH_OPPORTUNITY_EXPORTS.csv ({len(high_opp)} rows)")

    # Export 2: Mega growth only (ultra-compact)
    mega = merged[merged['Opportunity'] == 'MEGA_GROWTH'].sort_values('Value_2023_M', ascending=False)
    mega[['Commodity', 'Value_2023_M', 'Growth_5yr_%']].to_csv(
        out / 'MEGA_GROWTH_EXPORTS.csv',
        index=False
    )
    print(f"✓ MEGA_GROWTH_EXPORTS.csv ({len(mega)} rows)")

    # Export 3: By category (compact analysis)
    print("\n" + "="*80)
    print("OPPORTUNITY CLASSIFICATION")
    print("="*80)
    for cat in OPPORTUNITY_CATEGORIES + ['PREMIUM_STABLE']:
        subset = merged[merged['Opportunity'] == cat]
        avg_growth = subset['Growth_5yr_%'].mean()
        avg_value = subset['Value_2023_M'].mean()
        print(f"{cat:25} | Count: {len(subset):4} | Avg Value: ${avg_value:8,.0f}M | Avg Growth: {avg_growth:6.1f}%")

    # Export 4: JSON for programmatic use
    top_by_category = {}
    for cat in OPPORTUNITY_CATEGORIES:
        subset = merged[merged['Opportunity'] == cat].nlargest(5, 'Value_2023_M')
        top_by_category[cat] = subset[['Commodity', 'Value_2023_M', 'Growth_5yr_%']].to_dict('records')

    with open(out / 'TOP_OPPORTUNITIES.json', 'w') as f:
        json.dump(top_by_category, f, indent=2, default=str)
    print("\n✓ TOP_OPPORTUNITIES.json (top 5 per category)")

    return merged

if __name__ == '__main__':
    create_optimized_export()
    print(f"\n✓ Token-optimized exports created in {output_dir()}/")
