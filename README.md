# 📦 India Trade & Export Analysis (2020–2026)

<!-- how-to-use-with-ai -->
> **New here?** See [How to use this repo with AI (Claude, Gemini, ChatGPT)](HOW_TO_USE_WITH_AI.md) — clone it, paste it into an AI tool, and ask in plain English.


[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/herrrickshaw/india-trade-export-analysis/blob/main/notebooks/colab_test.ipynb)

Analysis of India's **import/export trade**, fiscal reserves, and high-opportunity
export sectors across the post-pandemic period. (Original detailed notes preserved in
the `*_ANALYSIS.md` / `*_SUMMARY.md` files.)

## Contents

| File | What it does |
|---|---|
| `export_analysis.py` | Core export analysis |
| `export_extended_analysis.py` | Extended 2020–2026 trend analysis |
| `export_insights.py` | Insight generation |
| `export_opportunities.py` | High-opportunity export identification |
| `import_export_comparison.py` | Import vs export comparison |
| `markitdown-preprocessor.py` | Source-doc preprocessing |
| `*.md` | Writeups — executive summary, YoY trends, RBI reserves vs trade deficit, tax/fiscal, 5-year post-pandemic comparison |
| `*.csv`, `*.json` | Datasets — extended analysis, mega-growth & high-opportunity exports, top opportunities |

## Data inputs (not in this repo)

The scripts read the DGCI&S TradeStat-Eidb commodity-wise workbooks, which are **not committed**.
Download them from <https://tradestat.commerce.gov.in/eidb> and save them in one folder under these names:

- `TradeStat-Eidb-Export-Commodity-wise 2020.xlsx`
- `TradeStat-Eidb-Export-Commodity-wise2022.xlsx`
- `TradeStat-Eidb-Export-Commodity-wise.xlsx`
- `TradeStat-Eidb-Import-Commodity-wise.xlsx` (only `import_export_comparison.py`)

Tell the scripts where they are with `--data-dir DIR` or `TRADESTAT_DIR=DIR`; outputs are written to
`--out-dir DIR` / `TRADESTAT_OUT_DIR` (default: current directory). Without it a script exits with a message
listing the expected files (see `tradestat_config.py`).

## Run
```bash
export TRADESTAT_DIR="$HOME/Downloads/import export data"   # or pass --data-dir
python export_analysis.py
python export_extended_analysis.py --out-dir out
python export_opportunities.py --out-dir out
```

## Known data issues (found 2026-10-23)

1. **Totals were 2x.** The workbook has a grand-total row ("India's Total Export"). The scripts summed it with the
   line items, so every total read exactly twice the truth (the old $583.6B / $902.1B / $875.4B are 2 x $291.8B /
   $451.1B / $437.7B; the `*.md` writeups carried the same numbers). Scripts now drop that row
   (`tradestat_config.drop_total_row`) and print workbook total vs line-item sum. Verified on synthetic workbooks
   in the real layout: raw sum 9,640 -> 4,820 = the total row.
2. **Committed CSV line items sum to +5.2% over the total row** (`EXTENDED_ANALYSIS_2020_2026.csv`: 2023 items
   $460,482.71M vs total row $437,704.58M, +5.20%; 2020 items $331,378.23M vs $291,808.48M, +13.56%). Cause: the
   scripts joined 2020 to 2023 on the `Commodity` text, which repeats across HS codes. Many-to-many joins multiply
   rows: of 14,979 line rows, 5,183 repeat a commodity name, in blocks of 4, 9, 16, 25, 36, 64 rows (n x n). On a
   synthetic file with 8 repeated descriptions the old join gave 97 rows from 40 and a 2020 sum of 16,500 vs a true
   4,820. Scripts now join on `HSCode` + `Commodity`. The committed CSV/JSON files were **not** regenerated (the
   workbooks are unavailable here): do not sum them, and use the `India's Total Export` row for totals.
3. **Period labels.** Cross-checking against [`india-trade-data-analysis`](https://github.com/herrrickshaw/india-trade-data-analysis)
   (TRADESTAT, retrieved 2026-07-18): the "2020" total equals FY2020-21 ($291,808.5M), "2022" equals FY2022-23
   ($451,070.0M) and the "2023" total ($437,704.58M) equals FY2024-25 ($437,704.5M), not FY2023-24 ($437,072.1M).
   The "2020-2023, 3-year" growth/CAGR framing is therefore doubtful; verify against the workbook header.
4. `export_analysis.py` reads the sheet without `skiprows=2` and auto-detects columns; it was not changed beyond
   paths and the total-row drop and may not detect columns on the real layout.

## Reference data refresh (2026-07-18 vintage)

`data/india_merchandise_trade_totals_FY2018-19_to_FY2025-26.csv`: merchandise exports/imports/balance, US$ million,
DGCI&S TRADESTAT 2-digit HS totals as published in `india-trade-data-analysis`
(`data/tradestat_hsn_export_import_2018-19_to_2025-26.json`, retrieved 2026-07-18; FY2025-26 provisional, source
updated 19 May 2026). Latest: FY2025-26 exports $441,745.9M, imports $776,013.7M, balance -$334,267.8M
(computed from the rounded totals; PIB cites a $333.19bn deficit per the sibling repo's cross-validation).
Not refreshed: commodity-level (HS8) data and the CSVs above, which need the TradeStat workbooks.

## Related repos
- [`fuel-retail-outlets`](https://github.com/herrrickshaw/fuel-retail-outlets)
- [`global-market-scanners`](https://github.com/herrrickshaw/global-market-scanners)

## Notes
Built from public trade/fiscal data sources. Indicative analysis, not official statistics.
