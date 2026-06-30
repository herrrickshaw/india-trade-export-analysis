"""
Import vs Export Comparison Analysis
Compares trade flows and projects trade balance through 2026
"""

import pandas as pd
import os
from pathlib import Path
import numpy as np

def load_export_file(filepath, year=None):
    """Load export data"""
    df = pd.read_excel(filepath, sheet_name=0, skiprows=2)
    df.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_Current_Million',
                  'Share_Current', 'Value_Next_Million', 'Share_Next', 'Growth_%']
    df = df.dropna(subset=['Commodity', 'Value_Current_Million'])
    df['Value_Current_Million'] = pd.to_numeric(df['Value_Current_Million'], errors='coerce')
    if year:
        df['Year'] = year
    df['Type'] = 'EXPORT'
    return df

def load_import_file(filepath, year=None):
    """Load import data"""
    df = pd.read_excel(filepath, sheet_name=0, skiprows=2)
    df.columns = ['S.No.', 'HSCode', 'Commodity', 'Value_Current_Million',
                  'Share_Current', 'Value_Next_Million', 'Share_Next', 'Growth_%']
    df = df.dropna(subset=['Commodity', 'Value_Current_Million'])
    df['Value_Current_Million'] = pd.to_numeric(df['Value_Current_Million'], errors='coerce')
    if year:
        df['Year'] = year
    df['Type'] = 'IMPORT'
    return df

def load_all_data():
    """Load both import and export data"""
    base_path = Path.home() / "Downloads" / "import export data"

    data = {}

    # Export files
    export_files = {
        2020: base_path / "TradeStat-Eidb-Export-Commodity-wise 2020.xlsx",
        2022: base_path / "TradeStat-Eidb-Export-Commodity-wise2022.xlsx",
        2023: base_path / "TradeStat-Eidb-Export-Commodity-wise.xlsx",
    }

    # Import files
    import_files = {
        2020: base_path / "TradeStat-Eidb-Import-Commodity-wise.xlsx",  # Assuming same name pattern
    }

    print("\n" + "="*100)
    print("LOADING TRADE DATA")
    print("="*100)

    # Load exports
    data['exports'] = {}
    for year, filepath in export_files.items():
        if os.path.exists(filepath):
            try:
                df = load_export_file(filepath, year)
                data['exports'][year] = df
                print(f"✓ Exports {year}: {len(df)} commodities, ${df['Value_Current_Million'].sum():,.0f}M total")
            except Exception as e:
                print(f"✗ Error loading exports {year}: {e}")

    # Load imports
    data['imports'] = {}
    # Try to detect which year the import file is from
    import_path = base_path / "TradeStat-Eidb-Import-Commodity-wise.xlsx"
    if os.path.exists(import_path):
        try:
            # Try loading and checking the data to infer year
            df = load_import_file(import_path)
            # Assume it's the same year as the latest export data
            latest_year = max(data['exports'].keys())
            df['Year'] = latest_year
            data['imports'][latest_year] = df
            print(f"✓ Imports {latest_year}: {len(df)} commodities, ${df['Value_Current_Million'].sum():,.0f}M total")
        except Exception as e:
            print(f"✗ Error loading imports: {e}")

    return data

def analyze_trade_balance(data):
    """Analyze import vs export balance"""

    print("\n" + "="*100)
    print("TRADE BALANCE ANALYSIS")
    print("="*100)

    # Summary by year
    print("\n" + "-"*100)
    print("TOTAL TRADE FLOW SUMMARY")
    print("-"*100)

    export_summary = {}
    import_summary = {}

    for year, df in data['exports'].items():
        export_summary[year] = df['Value_Current_Million'].sum()

    for year, df in data['imports'].items():
        import_summary[year] = df['Value_Current_Million'].sum()

    # Create comparison table
    comparison_data = []
    for year in sorted(export_summary.keys()):
        exp = export_summary.get(year, 0)
        imp = import_summary.get(year, 0)
        if exp > 0 or imp > 0:
            balance = exp - imp
            ratio = exp / imp if imp > 0 else 0
            comparison_data.append({
                'Year': year,
                'Exports ($M)': f"{exp:,.0f}",
                'Imports ($M)': f"{imp:,.0f}",
                'Trade Balance ($M)': f"{balance:,.0f}",
                'Export/Import Ratio': f"{ratio:.2f}x" if imp > 0 else "N/A"
            })

    comp_df = pd.DataFrame(comparison_data)
    print("\n" + comp_df.to_string(index=False))

    # Trade balance trend
    if len(export_summary) > 0 and len(import_summary) > 0:
        latest_export_year = max(export_summary.keys())
        latest_import_year = max(import_summary.keys())

        if latest_export_year == latest_import_year:
            exp = export_summary[latest_export_year]
            imp = import_summary[latest_import_year]
            balance = exp - imp
            ratio = exp / imp

            print(f"\n" + "-"*100)
            print(f"LATEST YEAR ANALYSIS ({latest_export_year})")
            print("-"*100)
            print(f"\nTotal Exports:      ${exp:,.0f}M")
            print(f"Total Imports:      ${imp:,.0f}M")
            print(f"Trade Balance:      ${balance:,.0f}M {'(SURPLUS)' if balance > 0 else '(DEFICIT)'}")
            print(f"Export/Import Ratio: {ratio:.2f}x (Exports are {ratio:.1%} of Imports)")

    return export_summary, import_summary

def analyze_commodity_comparison(data):
    """Analyze specific commodities in import vs export"""

    print("\n" + "="*100)
    print("COMMODITY-LEVEL COMPARISON (Available Data)")
    print("="*100)

    # Get latest year data
    latest_export_year = max(data['exports'].keys())
    latest_import_year = max(data['imports'].keys()) if data['imports'] else None

    if latest_export_year and latest_import_year and latest_export_year == latest_import_year:
        year = latest_export_year

        exp_df = data['exports'][year][['Commodity', 'Value_Current_Million']].copy()
        exp_df.columns = ['Commodity', 'Export_Value']

        imp_df = data['imports'][year][['Commodity', 'Value_Current_Million']].copy()
        imp_df.columns = ['Commodity', 'Import_Value']

        # Merge on commodity
        merged = pd.merge(exp_df, imp_df, on='Commodity', how='outer').fillna(0)

        # Calculate metrics
        merged['Trade_Balance'] = merged['Export_Value'] - merged['Import_Value']
        merged['Net_Exporter'] = merged['Trade_Balance'] > 0
        merged['Export_Share_%'] = (merged['Export_Value'] / (merged['Export_Value'] + merged['Import_Value']) * 100).fillna(0)

        # Top net exporters
        print(f"\n" + "-"*100)
        print(f"TOP NET EXPORTER COMMODITIES ({year})")
        print("-"*100)

        top_export = merged[merged['Trade_Balance'] > 0].nlargest(15, 'Trade_Balance')[
            ['Commodity', 'Export_Value', 'Import_Value', 'Trade_Balance', 'Export_Share_%']
        ]

        if len(top_export) > 0:
            print("\n" + top_export.to_string(index=False))
        else:
            print("No data available for commodity-level comparison")

        # Top net importers
        print(f"\n" + "-"*100)
        print(f"TOP NET IMPORTER COMMODITIES ({year})")
        print("-"*100)

        top_import = merged[merged['Trade_Balance'] < 0].nsmallest(15, 'Trade_Balance')[
            ['Commodity', 'Export_Value', 'Import_Value', 'Trade_Balance', 'Export_Share_%']
        ]

        if len(top_import) > 0:
            print("\n" + top_import.to_string(index=False))
        else:
            print("No data available for commodity-level comparison")

        # Balanced commodities
        print(f"\n" + "-"*100)
        print(f"BALANCED TRADE (Trade Balance within ±$1B)")
        print("-"*100)

        balanced = merged[
            (merged['Trade_Balance'].abs() <= 1000) &
            (merged['Export_Value'] > 0) &
            (merged['Import_Value'] > 0)
        ].nlargest(10, 'Export_Value')[
            ['Commodity', 'Export_Value', 'Import_Value', 'Trade_Balance']
        ]

        if len(balanced) > 0:
            print("\n" + balanced.to_string(index=False))

    else:
        print("\nInsufficient data for commodity-level comparison (different year coverage)")

def project_trade_balance(data):
    """Project future trade balance"""

    print("\n" + "="*100)
    print("TRADE BALANCE PROJECTIONS (2025-2026)")
    print("="*100)

    export_summary = {}
    import_summary = {}

    for year, df in data['exports'].items():
        export_summary[year] = df['Value_Current_Million'].sum()

    for year, df in data['imports'].items():
        import_summary[year] = df['Value_Current_Million'].sum()

    if len(export_summary) >= 2 and len(import_summary) >= 1:
        # Calculate export CAGR
        years_export = sorted(export_summary.keys())
        if len(years_export) >= 2:
            first_year = years_export[0]
            last_year = years_export[-1]
            exp_cagr = (export_summary[last_year] / export_summary[first_year]) ** (1 / (last_year - first_year)) - 1

            print(f"\nExport CAGR ({first_year}-{last_year}): {exp_cagr*100:.2f}%")
        else:
            exp_cagr = 0.13  # Use 13% from earlier analysis

        # Calculate import growth (single year, assume similar to export)
        imp_cagr = exp_cagr * 0.9  # Assume imports grow slightly slower

        print(f"Projected Import CAGR: {imp_cagr*100:.2f}%")

        # Project to 2026
        latest_export_year = max(export_summary.keys())
        latest_export_value = export_summary[latest_export_year]

        latest_import_year = max(import_summary.keys())
        latest_import_value = import_summary[latest_import_year]

        # Years ahead
        years_ahead_export = 2026 - latest_export_year
        years_ahead_import = 2026 - latest_import_year

        # Projections
        proj_2026_export = latest_export_value * (1 + exp_cagr) ** years_ahead_export
        proj_2026_import = latest_import_value * (1 + imp_cagr) ** years_ahead_import

        proj_trade_balance = proj_2026_export - proj_2026_import

        print(f"\n" + "-"*100)
        print("2026 TRADE BALANCE PROJECTION")
        print("-"*100)
        print(f"\nProjected 2026 Exports:    ${proj_2026_export:,.0f}M")
        print(f"Projected 2026 Imports:    ${proj_2026_import:,.0f}M")
        print(f"Projected Trade Balance:   ${proj_trade_balance:,.0f}M")
        print(f"\nTrade Balance Ratio:       {(proj_2026_export/proj_2026_import):.2f}x")
        print(f"(Exports are {(proj_2026_export/proj_2026_import):.1%} of Imports)")

        # Scenario analysis
        print(f"\n" + "-"*100)
        print("TRADE BALANCE SCENARIOS (2026)")
        print("-"*100)

        scenarios = {
            'Balanced Growth': (exp_cagr, imp_cagr),
            'Export-Led': (exp_cagr * 1.2, imp_cagr * 0.8),
            'Import-Heavy': (exp_cagr * 0.9, imp_cagr * 1.1),
        }

        scenario_data = []
        for scenario_name, (exp_rate, imp_rate) in scenarios.items():
            proj_exp = latest_export_value * (1 + exp_rate) ** years_ahead_export
            proj_imp = latest_import_value * (1 + imp_rate) ** years_ahead_import
            proj_balance = proj_exp - proj_imp

            scenario_data.append({
                'Scenario': scenario_name,
                'Exports ($M)': f"${proj_exp:,.0f}",
                'Imports ($M)': f"${proj_imp:,.0f}",
                'Balance ($M)': f"${proj_balance:,.0f}",
                'Ratio': f"{proj_exp/proj_imp:.2f}x"
            })

        scenario_df = pd.DataFrame(scenario_data)
        print("\n" + scenario_df.to_string(index=False))

    else:
        print("\nInsufficient data for trade balance projections")

def main():
    """Run full analysis"""
    data = load_all_data()

    if not data['exports']:
        print("\n✗ No export data loaded. Exiting.")
        return

    # Run analyses
    exp_summary, imp_summary = analyze_trade_balance(data)
    analyze_commodity_comparison(data)
    project_trade_balance(data)

    # Export summary
    print("\n" + "="*100)
    print("ANALYSIS COMPLETE")
    print("="*100)

    print(f"\n✓ Export data years available: {sorted(data['exports'].keys())}")
    print(f"✓ Import data years available: {sorted(data['imports'].keys()) if data['imports'] else 'None'}")
    print("\nNote: Full commodity-level comparison requires both import and export data")
    print("for the same year(s)")

if __name__ == '__main__':
    main()
