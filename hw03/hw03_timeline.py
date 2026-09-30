"""
MIS3060 - HW03: Corporate Events Timeline
Author: Emma Maguire (Villanova University)

Joins the two HW03 datasets and places every executive event relative to the
nearest earnings filing for the same company.

  1. For each executive event, finds the nearest earnings filing_date for the
     same company and computes days_to_nearest_earnings (absolute # of days)
  2. Labels event_timing:
        'same week'       -> within 7 days (either side) of that earnings filing
        'before earnings' -> event came before the nearest earnings filing
        'after earnings'  -> event came after the nearest earnings filing
  3. Saves the combined table to hw03/corporate_events_timeline.csv
  4. Prints a per-company summary of the events and their timing
  5. Prints a final before vs. after count across all five companies

Inputs:  hw03/earnings_history.csv, hw03/executive_events.csv
Run from your project folder:  python hw03/hw03_timeline.py
Requirements:  pip install pandas
"""

from pathlib import Path

import pandas as pd

# Paths are anchored to this script's folder (hw03/), so the script works no
# matter which directory you run it from.
HW03_DIR = Path(__file__).resolve().parent
EARNINGS_CSV = HW03_DIR / "earnings_history.csv"
EVENTS_CSV = HW03_DIR / "executive_events.csv"
OUTPUT_CSV = HW03_DIR / "corporate_events_timeline.csv"

SAME_WEEK_DAYS = 7

# --------------------------------------------------------------------------
# Load data
# --------------------------------------------------------------------------
# dtype=str keeps CIKs like "0000320193" from losing their leading zeros.
earnings = pd.read_csv(EARNINGS_CSV, dtype=str)
events = pd.read_csv(EVENTS_CSV, dtype=str)

earnings["filing_date"] = pd.to_datetime(earnings["filing_date"])
events["filing_date"] = pd.to_datetime(events["filing_date"])

# Both tables have a filing_date column; rename them so the combined table
# makes clear which date is which.
events = events.rename(columns={"filing_date": "event_filing_date"})
earnings = earnings.rename(columns={"filing_date": "earnings_filing_date"})

# Earnings-only columns we will attach to each event (company/ticker/cik are
# shared keys and already on the events table).
EARNINGS_COLS = ["earnings_filing_date", "period", "revenue_reported",
                 "eps_diluted", "net_income"]

# --------------------------------------------------------------------------
# Steps 1 & 2: nearest earnings filing + timing category
# --------------------------------------------------------------------------
def classify(signed_days):
    """signed_days = event date minus earnings date (negative = event first)."""
    if abs(signed_days) <= SAME_WEEK_DAYS:
        return "same week"
    return "before earnings" if signed_days < 0 else "after earnings"


rows = []
for _, event in events.iterrows():
    company_earnings = earnings[earnings["cik"] == event["cik"]]

    if company_earnings.empty:
        # No earnings data for this company -- keep the event, flag it.
        row = event.to_dict()
        row.update({col: pd.NA for col in EARNINGS_COLS})
        row["days_to_nearest_earnings"] = pd.NA
        row["event_timing"] = "no earnings data"
        rows.append(row)
        continue

    signed = (event["event_filing_date"]
              - company_earnings["earnings_filing_date"]).dt.days
    # Nearest = smallest absolute gap. On an exact tie, idxmin keeps the first
    # row in the file (the more recent filing, since the CSV is newest-first).
    nearest_idx = signed.abs().idxmin()
    nearest = company_earnings.loc[nearest_idx]
    signed_days = int(signed.loc[nearest_idx])

    row = event.to_dict()
    row.update({col: nearest[col] for col in EARNINGS_COLS})
    row["days_to_nearest_earnings"] = abs(signed_days)
    row["event_timing"] = classify(signed_days)
    row["_signed_days"] = signed_days  # helper for the printout only
    rows.append(row)

timeline = pd.DataFrame(rows)

# --------------------------------------------------------------------------
# Step 3: save combined table
# --------------------------------------------------------------------------
event_cols = [c for c in events.columns]  # company, ticker, cik, event_filing_date, ...
output_cols = event_cols + EARNINGS_COLS + ["days_to_nearest_earnings",
                                            "event_timing"]
timeline = timeline.sort_values(["company", "event_filing_date"])

out = timeline[output_cols].copy()
out["event_filing_date"] = out["event_filing_date"].dt.strftime("%Y-%m-%d")
out["earnings_filing_date"] = pd.to_datetime(
    out["earnings_filing_date"]).dt.strftime("%Y-%m-%d")
out.to_csv(OUTPUT_CSV, index=False)
print(f"Saved {len(out)} rows x {len(out.columns)} columns to {OUTPUT_CSV}\n")

# --------------------------------------------------------------------------
# Step 4: per-company summary
# --------------------------------------------------------------------------
print("=" * 78)
print("EXECUTIVE EVENTS RELATIVE TO NEAREST EARNINGS ANNOUNCEMENT")
print("=" * 78)

# Loop over every company in the earnings file so a company with zero
# executive events still shows up in the summary.
for company in sorted(set(earnings["company"]) | set(events["company"])):
    group = timeline[timeline["company"] == company]
    ticker = (group["ticker"].iloc[0] if not group.empty else
              earnings.loc[earnings["company"] == company, "ticker"].iloc[0])
    print(f"\n{company} ({ticker}) - {len(group)} executive event(s)")

    if group.empty:
        print("   No executive events in the past 12 months")
        continue

    for _, r in group.iterrows():
        if pd.isna(r["days_to_nearest_earnings"]):
            detail = "no earnings data to compare"
        else:
            direction = "before" if r["_signed_days"] < 0 else "after"
            if r["_signed_days"] == 0:
                direction = "on the same day as"
            detail = (f"{r['event_timing'].upper():<15} "
                      f"{r['days_to_nearest_earnings']:>3} days {direction} "
                      f"{r['period']} earnings "
                      f"({pd.Timestamp(r['earnings_filing_date']):%Y-%m-%d})")
        print(f"   {r['event_filing_date']:%Y-%m-%d} | {r['event_type']:<11} | "
              f"{r['person_name']:<22} | {detail}")

# --------------------------------------------------------------------------
# Step 5: final counts
# --------------------------------------------------------------------------
counts = timeline["event_timing"].value_counts()
before = counts.get("before earnings", 0)
after = counts.get("after earnings", 0)
same_week = counts.get("same week", 0)

print("\n" + "=" * 78)
print("FINAL COUNT - ALL FIVE COMPANIES")
print("=" * 78)
print(f"Before earnings : {before}")
print(f"After earnings  : {after}")
print(f"Same week (within {SAME_WEEK_DAYS} days, either side): {same_week}")
if "no earnings data" in counts:
    print(f"No earnings data: {counts['no earnings data']}")
print(f"Total events    : {len(timeline)}")
