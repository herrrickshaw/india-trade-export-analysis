"""Synthetic TradeStat workbooks in the real layout: two title rows and a header row, then
S.No., HSCode, Commodity, value, share, next-year value, next-year share, growth, with a
grand-total row ("India's Total Export") among the line items."""
import pandas as pd

import tradestat_config as cfg

COLS = ["S.No.", "HSCode", "Commodity", "Value", "Share", "Next", "NextShare", "Growth"]


def write_workbook(path, rows, total_label="India's Total Export"):
    """rows: [(hs, commodity, value, growth)]. Appends a grand-total row equal to the sum."""
    body = [[i + 1, hs, name, val, 0.0, 0.0, 0.0, g] for i, (hs, name, val, g) in enumerate(rows)]
    total = sum(r[2] for r in rows)
    body.append([len(rows) + 1, None, total_label, total, 100.0, 0.0, 0.0, 0.0])
    junk = pd.DataFrame([["TradeStat title"] + [None] * 7, [None] * 8, COLS])      # two title rows + the header row
    df = pd.concat([junk, pd.DataFrame(body)], ignore_index=True)
    df.to_excel(path, header=False, index=False)
    return total


# (hs, name, value_2020, value_2023, growth_%_in_2023_file)
BOOK = [
    ("01", "Alpha", 100.0, 200.0, 25.0),      # >50 in 2023, growth 100%
    ("02", "Bravo", 40.0, 60.0, 20.0),        # 50% growth; growth_% exactly 20 (strict > 20)
    ("03", "Charlie", 50.0, 50.0, 30.0),      # exactly 50 in 2023: not "> 50"
    ("04", "Delta", 10.0, 11.0, 5.0),
    ("05", "Echo", 5.0, 20.0, 40.0),          # emerging: 10 < v <= 50 and growth 300%
    ("06", "Foxtrot", 5.0, 10.0, 40.0),       # exactly 10: not > 10
    ("07", "Golf", 10.0, 50.0, 40.0),         # exactly 50: still <= 50 -> emerging (400%)
    ("08", "Hotel", 20.0, 30.0, 40.0),        # exactly 50% growth: not > 50
    ("09", "India", 400.0, 501.0, 10.0),      # premium (> 500)
    ("10", "Juliet", 400.0, 500.0, 10.0),     # exactly 500: not premium
    ("11", "Kilo", 0.5, 0.9, 99.0),           # value <= 1
]


def install_books(dirpath, years=(2020, 2022, 2023), book=BOOK):
    dirpath.mkdir(exist_ok=True)
    totals = {}
    for y in years:
        idx = {2020: 2, 2022: 2, 2023: 3}[y]
        rows = [(hs, nm, (v20 if y != 2023 else v23), g) for hs, nm, v20, v23, g in book]
        totals[y] = write_workbook(dirpath / cfg.EXPORT_FILENAMES[y], rows)
    return totals
