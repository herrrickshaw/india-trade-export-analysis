"""Value-per-unit and 5-year growth screen over the commodity-wise export workbooks (flat header layout)."""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from trade_common import LOAD_ERRORS, export_paths

warnings.filterwarnings('ignore')

HIGH_VPU_MULTIPLE = 2     # "high value" = value per unit above this multiple of the median
MIN_VALUE_GROWTH_PCT = 10


def extract_year(filepath):
    """Extract year from filename"""
    if "2020" in filepath:
        return 2020
    elif "2022" in filepath:
        return 2022
    else:
        return 2023  # Default to latest


def load_workbooks(export_files) -> Dict[int, pd.DataFrame]:
    """Read the first sheet of each existing workbook, keyed by the year inferred from its filename."""
    all_data = {}
    for file_path in export_files:
        if Path(file_path).exists():
            try:
                # Try to read with different sheet names
                xls = pd.ExcelFile(file_path)
                sheet_name = xls.sheet_names[0]
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                year = extract_year(str(file_path))
                all_data[year] = df
                print(f"✓ Loaded {Path(file_path).name} (Year: {year})")
                print(f"  Shape: {df.shape}, Columns: {list(df.columns)[:5]}...\n")
            except LOAD_ERRORS as e:
                print(f"✗ Error reading {Path(file_path).name}: {e}\n")
    return all_data


def find_columns(columns):
    """Return (commodity, value, quantity) column names found by keyword; None where absent."""
    value_col = qty_col = commodity_col = None
    for col in columns:
        col_lower = col.lower()
        if 'commodity' in col_lower or 'product' in col_lower or 'description' in col_lower:
            commodity_col = col
        if 'value' in col_lower and value_col is None:
            value_col = col
        if any(x in col_lower for x in ['qty', 'quantity', 'volume', 'units']):
            qty_col = col
    return commodity_col, value_col, qty_col


def standardize(all_data: Dict[int, pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Stack all years into Commodity / Value_USD / Quantity / Year / Value_Per_Unit; None if nothing usable."""
    combined = []
    for year, df in sorted(all_data.items()):
        df['Year'] = year
        commodity_col, value_col, qty_col = find_columns(df.columns)
        if commodity_col and value_col and qty_col:
            subset = df[[commodity_col, value_col, qty_col, 'Year']].copy()
            subset.columns = ['Commodity', 'Value_USD', 'Quantity', 'Year']
            combined.append(subset)
        else:
            print(f"Warning: Could not identify columns for {year}")
            print(f"  Found: Commodity={commodity_col}, Value={value_col}, Qty={qty_col}")

    if not combined:
        return None
    df_all = pd.concat(combined, ignore_index=True)
    df_all['Value_USD'] = pd.to_numeric(df_all['Value_USD'], errors='coerce')
    df_all['Quantity'] = pd.to_numeric(df_all['Quantity'], errors='coerce')
    df_all = df_all.dropna(subset=['Value_USD', 'Quantity'])
    df_all['Value_Per_Unit'] = df_all['Value_USD'] / df_all['Quantity']
    return df_all


def high_value_commodities(df_all: pd.DataFrame, median_vpu: float) -> pd.DataFrame:
    """Commodities with any year's value per unit above ``HIGH_VPU_MULTIPLE`` x median, highest first."""
    high_value = df_all[df_all['Value_Per_Unit'] > median_vpu * HIGH_VPU_MULTIPLE].groupby('Commodity').agg({
        'Value_USD': 'sum',
        'Quantity': 'sum',
        'Value_Per_Unit': 'mean',
        'Year': 'nunique'
    }).reset_index()
    return high_value.sort_values('Value_Per_Unit', ascending=False)


def growth_summary(df_all: pd.DataFrame) -> pd.DataFrame:
    """Per-commodity first-to-last-year value and quantity growth (%), average unit value, latest value."""
    growth = df_all.groupby(['Commodity', 'Year']).agg({
        'Value_USD': 'sum',
        'Quantity': 'sum'
    }).reset_index()

    rows = []
    for commodity in df_all['Commodity'].unique():
        commodity_data = growth[growth['Commodity'] == commodity].sort_values('Year')
        if len(commodity_data) >= 2:
            first_year = commodity_data.iloc[0]
            last_year = commodity_data.iloc[-1]

            value_growth = ((last_year['Value_USD'] - first_year['Value_USD']) / first_year['Value_USD'] * 100) if first_year['Value_USD'] > 0 else 0
            qty_growth = ((last_year['Quantity'] - first_year['Quantity']) / first_year['Quantity'] * 100) if first_year['Quantity'] > 0 else 0

            avg_vpu = commodity_data['Value_USD'].sum() / commodity_data['Quantity'].sum()

            rows.append({
                'Commodity': commodity,
                'Value_Growth_%': value_growth,
                'Qty_Growth_%': qty_growth,
                'Avg_Value_Per_Unit': avg_vpu,
                'Years_Tracked': len(commodity_data),
                'Latest_Value_USD': last_year['Value_USD']
            })
    return pd.DataFrame(rows).sort_values('Value_Growth_%', ascending=False)


def main() -> None:
    """Load, standardise and print the high-value / growth screens."""
    all_data = load_workbooks(export_paths().values())
    df_all = standardize(all_data)
    if df_all is None:
        print("No data could be loaded. Check file paths and Excel structure.")
        return

    print("\n" + "=" * 80)
    print("HIGH-VALUE EXPORTS (Value per Unit > Median)")
    print("=" * 80)
    median_vpu = df_all['Value_Per_Unit'].median()
    high_value = high_value_commodities(df_all, median_vpu)
    print(high_value.head(15).to_string())

    print("\n" + "=" * 80)
    print("5-YEAR GROWTH ANALYSIS")
    print("=" * 80)
    growth_df = growth_summary(df_all)
    high_growth = growth_df[
        (growth_df['Avg_Value_Per_Unit'] > median_vpu) &
        (growth_df['Value_Growth_%'] > MIN_VALUE_GROWTH_PCT)
    ]
    print("\nHIGH-VALUE EXPORTS WITH STRONG GROWTH (>10% value growth, 5-year period):")
    print(high_growth[['Commodity', 'Value_Growth_%', 'Qty_Growth_%', 'Avg_Value_Per_Unit', 'Latest_Value_USD']].to_string())

    print("\n" + "=" * 80)
    print("TOP OPPORTUNITIES: High Unit Value + Consistent Growth")
    print("=" * 80)
    opportunities = high_growth.nlargest(10, 'Avg_Value_Per_Unit')[
        ['Commodity', 'Avg_Value_Per_Unit', 'Value_Growth_%', 'Latest_Value_USD']
    ]
    print(opportunities.to_string())

    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total commodities analyzed: {df_all['Commodity'].nunique()}")
    print(f"Total export value: ${df_all['Value_USD'].sum():,.0f}")
    print(f"Median value per unit: ${median_vpu:,.2f}")
    print(f"High-value commodities (>2x median): {len(high_value)}")
    print(f"Growing commodities: {len(high_growth)}")


if __name__ == '__main__':
    main()
