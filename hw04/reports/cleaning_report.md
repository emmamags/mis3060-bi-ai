# Part E — Business report

**To:** Portfolio Committee  **Re:** Data warehouse extract, quality audit and cleaning

## Executive summary

The eight-table extract (five dimension tables, three fact tables) was audited, cleaned and re-validated before use in reporting. The audit found seven defects that would have broken joins or distorted figures. The most serious was that **0% of the 197,175 trade records could join to the securities table**, because security IDs were stored as "45.0" instead of "45". That single format issue would have left every holdings and security-level report blank. After cleaning, all 13 table relationships match 100%, and every table scores 100% on completeness, key uniqueness, type validity and rule checks.

No values were invented. Defects were fixed only where another column or table confirmed the correct value. Rows that could not be fixed were removed to traceable quarantine files: **25 duplicate client records** and **200 transactions ($10,888,495.37)** for clients that do not exist in the client table. Suspicious values that cannot be corrected were flagged, not changed.

## Cleaning summary

| Issue | Table | Rows | Action | How it was verified |
|---|---|---:|---|---|
| Security IDs stored as "45.0" | Transactions | 197,175 | Converted to "45" | All 500 IDs then match the securities table |
| Returns stored as text ("9.28%") | Portfolio snapshots | 300 | Converted to decimals | All 300 satisfy return − benchmark = alpha |
| States spelled out ("Pennsylvania") | Clients | 78 | Standardized to codes | All states now valid 2-letter codes |
| Same client entered twice | Clients | 25 | Quarantined | Every field matches the original except a one-letter last-name typo; no activity on the duplicates |
| Missing risk profile | Clients | 75 | Filled ("Balanced") + flagged | All 75 use benchmark 3, which only Balanced clients use |
| Transactions for unknown clients | Transactions | 200 | Quarantined | Client IDs not in the client table |
| Negative shares on Buy trades | Transactions | 835 | Sign corrected | All reconcile to amount = shares × price |
| AUM stuck at exactly $1,000 | Portfolio snapshots | 420 | Flagged only | 92 clients; true balance unknown |
| YTD returns beyond −60% / +100% | Portfolio snapshots | 2,157 | Flagged only | Still consistent with benchmark and alpha |

**Before and after (data quality scorecard):**

| Table | Measure | Raw | Clean |
|---|---|---:|---:|
| Transactions | Rows whose keys all join to their dimensions | 33.982% | 100% |
| Transactions | Values of the expected type | 90.545% | 100% |
| Transactions | Rows passing all business rules | 99.720% | 100% |
| Clients | Key uniqueness | 99.01% | 100% |
| Clients | Rows passing all business rules | 96.911% | 100% |
| Portfolio snapshots | Rows passing all business rules | 99.768% | 100% |

Every table reconciles: raw rows = clean rows + quarantined rows.

## Key judgment calls

**1. Removing the 25 duplicate clients.** Each duplicate matches an existing client on every field except a last name missing or gaining one letter ("Taylo" vs "Taylor"), and none has any fees, snapshots or transactions. Keeping them would overstate client counts and AUM by tier and advisor. *Risk:* if any were genuinely different people, a real client would be dropped. This is very unlikely given the exact matches and zero activity, and the rows are kept in a quarantine file if needed.

**2. Filling 75 missing risk profiles as "Balanced."** Benchmarks are assigned by risk profile, and benchmark 3 is used only by Balanced clients. All 75 clients use benchmark 3, so the profile was recovered from another table, not guessed. *Risk:* if the system assigns benchmark 3 by default when a profile is unknown, some of these clients may not be Balanced. The `risk_profile_imputed` flag lets analysts exclude them from risk-based reporting.

**3. Correcting the sign on 835 Buy trades.** The share counts were negative, but every trade amount equals the positive share count times price, and the trade type already says "Buy." Only the sign was wrong. *Risk:* if some were reversals, shares bought would be overstated. Low, since no amount or trade type indicates a reversal.

**4. Flagging rather than fixing implausible values.** The 420 snapshots at exactly $1,000 look like a system placeholder, and the 2,157 extreme returns are internally consistent (likely large deposits into small accounts). Neither can be corrected without inventing data, so both keep their values with a 0/1 flag. *Risk:* reports that ignore the flags will show false dips in AUM and distorted average returns.

Separately, outlier screening (IQR) flagged about 2–10% of values in AUM, fee and transaction amounts. These are mostly large high-net-worth accounts and trades, so a flag is a prompt to look, not evidence of an error.

## Limitations

- **$10.9M of transactions are excluded.** The 200 quarantined transactions belong to clients missing from the client table. Transaction totals are understated until the source team supplies those clients.
- **7,350 portfolio months have no fee charged.** These may be fee waivers or a missing data load. Fee revenue may be understated, and no fees were created to fill the gap.
- **Advisory fees do not reconcile across systems.** Advisory Fee transactions match the fee table in 0 of 7,653 client-months. Use the fee table for fee revenue and do not add the two together.
- **Flagged values remain in the data.** AUM floors, extreme returns and imputed risk profiles should be filtered or segmented using their flag columns.

---

*AI-assisted report — reviewed for factual accuracy on 10/26/2026 by Emma Maguire
