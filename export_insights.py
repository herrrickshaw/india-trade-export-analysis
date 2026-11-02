"""Print headline export insights (strong growers, 2020->2023 trend, premium exports, per-year totals)."""
from __future__ import annotations

import sys
import warnings

import pandas as pd

from trade_common import load_all_exports

warnings.filterwarnings('ignore')

# Screening thresholds (USD million / percent)
STRONG_MIN_VALUE_M = 1
STRONG_MIN_GROWTH_PCT = 20
TREND_MIN_VALUE_M = 50
TREND_MIN_GROWTH_PCT = 10
EMERGING_MIN_VALUE_M = 10
EMERGING_MAX_VALUE_M = 50
EMERGING_MIN_GROWTH_PCT = 50
PREMIUM_MIN_VALUE_M = 500


def strong_growers(latest_df: pd.DataFrame) -> pd.DataFrame:
    """Latest-year exports above the value and growth floors, largest first."""
    return latest_df[
        (latest_df['Value_Current_Million'] > STRONG_MIN_VALUE_M) &
        (latest_df['Growth_%'] > STRONG_MIN_GROWTH_PCT)
    ].sort_values('Value_Current_Million', ascending=False)


def merge_2020_2023(data: dict) -> pd.DataFrame:
    """Inner-join 2020 and 2023 values per commodity and add growth columns."""
    df_2020 = data[2020][['Commodity', 'Value_Current_Million']].rename(
        columns={'Value_Current_Million': 'Value_2020'})
    df_2023 = data[2023][['Commodity', 'Value_Current_Million']].rename(
        columns={'Value_Current_Million': 'Value_2023'})
    merged = pd.merge(df_2020, df_2023, on='Commodity', how='inner')
    merged['Value_2020'] = pd.to_numeric(merged['Value_2020'], errors='coerce')
    merged['Value_2023'] = pd.to_numeric(merged['Value_2023'], errors='coerce')
    merged = merged.dropna()
    merged['Growth_5yr_%'] = ((merged['Value_2023'] - merged['Value_2020']) /
                              merged['Value_2020'] * 100)
    merged['Absolute_Growth_M'] = merged['Value_2023'] - merged['Value_2020']
    return merged


def report_strong_growers(latest_df: pd.DataFrame, latest_year: int) -> None:
    print("\n" + "=" * 90)
    print("HIGH-VALUE EXPORTS WITH STRONG GROWTH (Last Available Year)")
    print("=" * 90)
    high_value_growth = strong_growers(latest_df)
    if len(high_value_growth) > 0:
        print(f"\nTop 20 exports: Value >$1M + Growth >20% (Year {latest_year}):")
        display = high_value_growth[['Commodity', 'Value_Current_Million', 'Growth_%']].head(20)
        print(display.to_string(index=False))
    else:
        print("No exports found with Value >$1M and Growth >20%")


def report_five_year_trend(data: dict) -> None:
    print("\n" + "=" * 90)
    print("5-YEAR GROWTH TREND ANALYSIS (2020 → 2023)")
    print("=" * 90)
    if 2020 not in data or 2023 not in data:
        return
    merged = merge_2020_2023(data)

    high_value_5yr = merged[
        (merged['Value_2023'] > TREND_MIN_VALUE_M) &
        (merged['Growth_5yr_%'] > TREND_MIN_GROWTH_PCT)
    ].sort_values('Value_2023', ascending=False)

    print("\nExports: Value $50M+ in 2023 + 10%+ Growth (2020-2023):")
    print(f"Found {len(high_value_5yr)} commodities\n")
    display_5yr = high_value_5yr[['Commodity', 'Value_2020', 'Value_2023',
                                  'Growth_5yr_%', 'Absolute_Growth_M']].head(25)
    print(display_5yr.to_string(index=False))

    print("\n" + "-" * 90)
    print("EMERGING HIGH-GROWTH EXPORTS ($10-50M in 2023, 50%+ Growth 2020-2023):")
    emerging = merged[
        (merged['Value_2023'] > EMERGING_MIN_VALUE_M) &
        (merged['Value_2023'] <= EMERGING_MAX_VALUE_M) &
        (merged['Growth_5yr_%'] > EMERGING_MIN_GROWTH_PCT)
    ].sort_values('Growth_5yr_%', ascending=False)
    print(f"Found {len(emerging)} commodities\n")
    display_emerging = emerging[['Commodity', 'Value_2020', 'Value_2023', 'Growth_5yr_%']].head(15)
    print(display_emerging.to_string(index=False))


def report_premium(latest_df: pd.DataFrame, latest_year: int) -> None:
    print("\n" + "=" * 90)
    print("PREMIUM EXPORTS (Likely high value-per-unit)")
    print("=" * 90)
    premium_candidates = latest_df[latest_df['Value_Current_Million'] > PREMIUM_MIN_VALUE_M].sort_values(
        'Value_Current_Million', ascending=False)
    print(f"\nTop premium exports ($500M+ value in {latest_year}):")
    display_premium = premium_candidates[['Commodity', 'Value_Current_Million', 'Growth_%']].head(15)
    print(display_premium.to_string(index=False))


def report_summary(data: dict) -> None:
    print("\n" + "=" * 90)
    print("SUMMARY STATISTICS")
    print("=" * 90)
    for year in sorted(data.keys()):
        df = data[year]
        total_value = df['Value_Current_Million'].sum()
        print(f"\n{year}:")
        print(f"  Total exports: ${total_value:,.0f}M")
        print(f"  Commodities: {len(df)}")
        print(f"  Avg value/commodity: ${df['Value_Current_Million'].mean():,.1f}M")
        print(f"  Median value/commodity: ${df['Value_Current_Million'].median():,.1f}M")
        top5 = df.nlargest(5, 'Value_Current_Million')[['Commodity', 'Value_Current_Million']]
        top5_str = ', '.join(
            f"{row['Commodity'][:30]}... (${row['Value_Current_Million']:,.0f}M)" for _, row in top5.iterrows())
        print(f"  Top 5 commodities: {top5_str}")


def main() -> int:
    """Load the export workbooks and print the four insight sections."""
    data = load_all_exports()
    if not data:
        print("No data loaded!")
        return 1
    latest_year = max(data.keys())
    latest_df = data[latest_year].copy()
    report_strong_growers(latest_df, latest_year)
    report_five_year_trend(data)
    report_premium(latest_df, latest_year)
    report_summary(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
