"""
Script:    hw02_countA.py
Purpose:   Count rows in fact_transactions.csv where txn_type is exactly 'Buy'
Dataset:   data/raw/fact_transactions.csv
Author:    Emma Maguire (MIS3060) - generated with Claude
Generated: 2026-09-23

How to run (from the project root folder):
    python hw02/hw02_countA.py
"""

import pandas as pd

df = pd.read_csv("data/raw/fact_transactions.csv")

# Exact match: case-sensitive, no trimming of spaces
buy_count = (df["txn_type"] == "Buy").sum()

print(f"Rows where txn_type == 'Buy': {buy_count:,}")
