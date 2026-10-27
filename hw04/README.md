# Process requirements- Read Me

## Structure

```
hw04/
├── Data/
│   ├── Raw/                      8 original CSVs (read only, not committed: excluded by .gitignore)
│   ├── clean/                    8 cleaned CSVs (same names and columns + flag columns) and README_clean.md
│   └── audit/                    cleaning_log.csv, value_changes.csv, quarantine_*.csv
├── scripts/
│   ├── 01_profile.py             Part A: generic profiler and four groups of data-quality checks
│   ├── 02_clean.py               Part C: cleaning program, one asserted step per decision
│   └── 03_validate.py            Part D: referential integrity, rule checks, reconciliations, IQR, scorecard
├── reports/
│   ├── profile_raw.csv           Part A: one row per column of every table
│   ├── dq_summary_raw.csv        Part A: every finding tagged ERROR / WARN / INFO
│   ├── data_quality_scorecard.csv  Part D: one row per table per stage (raw / clean)
│   ├── referential_integrity.csv   Part D: all 13 relationships, raw and clean
│   └── cleaning_report.md        Part E: report for the portfolio committee
├── decision_log.md               Part B: one entry per issue, written before the cleaning code
└── README.md
```

## How to run

From inside the `hw04` folder, with the 8 raw CSVs in `Data/Raw`:

```
python scripts/01_profile.py      # audit raw data      -> reports/profile_raw.csv, dq_summary_raw.csv
python scripts/02_clean.py        # clean               -> Data/clean/, Data/audit/
python scripts/03_validate.py     # validate raw + clean -> reports/data_quality_scorecard.csv, referential_integrity.csv
```

Run them in this order. `02_clean.py` stops with an assertion error if any fix does not do what `decision_log.md` says. Paths are written as `data/raw` etc.; this works on Windows, which ignores capitalization, but on Mac or Linux the folders would need to be named in lowercase.

## Claude Code review findings

Claude Code reviewed each script before it was committed. Findings and what I did about them:

### Part A: `01_profile.py`

| Finding | What I did |
|---|---|
| The plausibility check read "9.28%" as 9.28 instead of 0.0928 | **Fixed.** Percent strings are divided by 100 first; implausible returns went from 2,428 to 2,157 (271 false flags removed) |
| The Advisory Fee reconciliation compared against all fee types | **Fixed.** Compares against Advisory fees only (0 of 7,653 client-months match) |
| Dividends not in the shares × price check; `is_quarter_end` / `is_year_end` not verified | **Fixed.** Added all three checks (all pass) |
| Whitespace/case counting, NaN handling, merge row multiplication, FK text fallback, null tokens, date-format assumptions | **Reviewed, not changed.** None affects results on this data (no whitespace issues, unique keys, numeric FKs, ISO dates); would matter for messier input |
| Row and cross-table checks name specific tables and columns | **Not changed.** Business rules are table-specific; the column profile itself is fully generic |

### Part C: `02_clean.py`

| Finding | What I did |
|---|---|
| Quarantine files held partly cleaned rows | **Fixed.** Quarantine files now hold the original raw rows; `value_changes.csv` only lists kept rows |
| Counts were never checked against the audit (decision log said 836 / 76, script fixed 835 / 75) | **Fixed.** Every step asserts its count against the Part A audit; the script explains 836 → 835 (one was on a quarantined orphan) and 76 → 75 (one was on a quarantined duplicate). Decision log updated to match |
| The 2a flag assert could never fail; 2b had no assert | **Fixed.** Asserts now check counts against the audit, the alpha identity on flagged rows, and that flagging changed no values |
| Reconcile only compared row counts | **Fixed.** Added a key-level check (clean and quarantined keys are disjoint and together equal the raw keys) and RI checks on the clean tables |
| Duplicate check matched only 7 of 13 fields | **Fixed.** Now asserts every other field matches |
| Converted returns written with 6 decimals they don't have | **Fixed.** Written with 4 decimals |
| Fill value "Balanced" was hard-coded | **Fixed.** Taken from the benchmark → risk profile mapping the script verifies |
| Folder capitalization (`Data/Raw` vs `data/raw`) | **Not changed.** Works on Windows; noted above |

### Part D: `03_validate.py`

| Finding | What I did |
|---|---|
| RI function failed if tables were loaded with default `pd.read_csv` (needed for Assignment 5) | **Fixed.** Treats NaN as null and compares keys pandas already parsed as numbers by value |
| A table with all-blank keys showed 100% match | **Fixed.** Returns no match rate instead |
| Referential match was an average of rates, not a share of rows | **Fixed.** Now % of rows whose foreign keys all match (raw transactions 33.982% → clean 100%) |
| Raw `security_id` 0% match looked like 500 missing securities | **Fixed.** Added `match_rate_as_numbers` (100%) showing it is a format problem |
| "n/a" text in a numeric scorecard column | **Fixed.** Left blank instead |
| Clean completeness counted the added flag columns | **Fixed.** Completeness uses the raw columns only |
| Impossible dates passed type validity; console omitted some metrics; R5 could divide by zero | **Fixed.** All three |