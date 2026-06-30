"""
Generate token-optimized exports for Claude API analysis.
Reduces data to essentials: commodity, value, growth rates, and classification.
"""
import pandas as pd
import os

def create_optimized_export():
    """Create compact CSVs optimized for token reduction"""

    # Load 2020 and 2023 data
    df_2020 = pd.read_excel(
        "/Users/umashankar/Downloads/import export data/TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
        skiprows=2
    )
    df_2023 = pd.read_excel(
        "/Users/umashankar/Downloads/import export data/TradeStat-Eidb-Export-Commodity-wise.xlsx",
        skiprows=2
    )

    # Standardize columns
    cols = ['S.No.', 'HSCode', 'Commodity', 'Value_2020_M', 'Share_2020', 'Value_2023_M', 'Share_2023', 'Growth_%']
    df_2020.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_2020_M', 'Share', 'Value_Next_M', 'Share_Next', 'Growth_%']
    df_2023.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_2023_M', 'Share', 'Value_Next_M', 'Share_Next', 'Growth_%']

    # Merge
    merged = pd.merge(
        df_2020[['Commodity', 'Value_2020_M', 'HSCode']],
        df_2023[['Commodity', 'Value_2023_M', 'Growth_%']],
        on='Commodity',
        how='inner'
    )

    # Clean
    merged['Value_2020_M'] = pd.to_numeric(merged['Value_2020_M'], errors='coerce')
    merged['Value_2023_M'] = pd.to_numeric(merged['Value_2023_M'], errors='coerce')
    merged['Growth_%'] = pd.to_numeric(merged['Growth_%'], errors='coerce')
    merged = merged.dropna()

    # Calculate 5-year growth
    merged['Growth_5yr_%'] = ((merged['Value_2023_M'] - merged['Value_2020_M']) / merged['Value_2020_M'] * 100)

    # Classify by opportunity
    def classify_opportunity(row):
        if row['Value_2023_M'] > 5000 and row['Growth_5yr_%'] > 50:
            return 'MEGA_GROWTH'
        elif row['Value_2023_M'] > 1000 and row['Growth_5yr_%'] > 20:
            return 'HIGH_VALUE_GROWING'
        elif row['Value_2023_M'] > 100 and row['Growth_5yr_%'] > 100:
            return 'EMERGING_OPPORTUNITY'
        elif row['Value_2023_M'] > 500:
            return 'PREMIUM_STABLE'
        else:
            return 'OTHER'

    merged['Opportunity'] = merged.apply(classify_opportunity, axis=1)

    # Export 1: High-opportunity commodities only (for Claude analysis)
    high_opp = merged[merged['Opportunity'].isin([
        'MEGA_GROWTH', 'HIGH_VALUE_GROWING', 'EMERGING_OPPORTUNITY'
    ])].sort_values('Value_2023_M', ascending=False)

    high_opp[['Commodity', 'HSCode', 'Value_2020_M', 'Value_2023_M', 'Growth_5yr_%', 'Opportunity']].to_csv(
        '/Users/umashankar/Downloads/HIGH_OPPORTUNITY_EXPORTS.csv',
        index=False
    )
    print(f"✓ HIGH_OPPORTUNITY_EXPORTS.csv ({len(high_opp)} rows)")

    # Export 2: Mega growth only (ultra-compact)
    mega = merged[merged['Opportunity'] == 'MEGA_GROWTH'].sort_values('Value_2023_M', ascending=False)
    mega[['Commodity', 'Value_2023_M', 'Growth_5yr_%']].to_csv(
        '/Users/umashankar/Downloads/MEGA_GROWTH_EXPORTS.csv',
        index=False
    )
    print(f"✓ MEGA_GROWTH_EXPORTS.csv ({len(mega)} rows)")

    # Export 3: By category (compact analysis)
    print("\n" + "="*80)
    print("OPPORTUNITY CLASSIFICATION")
    print("="*80)
    for cat in ['MEGA_GROWTH', 'HIGH_VALUE_GROWING', 'EMERGING_OPPORTUNITY', 'PREMIUM_STABLE']:
        subset = merged[merged['Opportunity'] == cat]
        avg_growth = subset['Growth_5yr_%'].mean()
        avg_value = subset['Value_2023_M'].mean()
        print(f"{cat:25} | Count: {len(subset):4} | Avg Value: ${avg_value:8,.0f}M | Avg Growth: {avg_growth:6.1f}%")

    # Export 4: JSON for programmatic use
    import json
    top_by_category = {}
    for cat in ['MEGA_GROWTH', 'HIGH_VALUE_GROWING', 'EMERGING_OPPORTUNITY']:
        subset = merged[merged['Opportunity'] == cat].nlargest(5, 'Value_2023_M')
        top_by_category[cat] = subset[['Commodity', 'Value_2023_M', 'Growth_5yr_%']].to_dict('records')

    with open('/Users/umashankar/Downloads/TOP_OPPORTUNITIES.json', 'w') as f:
        json.dump(top_by_category, f, indent=2, default=str)
    print(f"\n✓ TOP_OPPORTUNITIES.json (top 5 per category)")

    return merged

if __name__ == '__main__':
    create_optimized_export()
    print("\n✓ Token-optimized exports created in /Users/umashankar/Downloads/")
