"""
Script:    hw02_countB.py
Purpose:   Count total rows in fact_transactions.csv, then subtract the rows
           where txn_type is Sell, Deposit, Withdrawal, Dividend, or
           Advisory Fee. What is left over should be the Buy rows.
Dataset:   data/raw/fact_transactions.csv
Author:    Emma Maguire (MIS3060) - generated with Claude
Generated: 2026-09-23

How to run (from the project root folder):
    python hw02/hw02_countB.py
"""

import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

total_rows = len(df)

other_types = ["Sell", "Deposit", "Withdrawal", "Dividend", "Advisory Fee"]
other_count = df["txn_type"].isin(other_types).sum()

remaining = total_rows - other_count

print(f"Total rows:                         {total_rows:,}")
print(f"Rows that are Sell, Deposit, Withdrawal, Dividend, or Advisory Fee: {other_count:,}")
print(f"Total minus those rows:             {remaining:,}")
