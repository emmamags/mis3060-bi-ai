# Part C — Cleaning program
## 1. Relationships

All are many-to-one, from the fact (or child) table to the dimension.

| From | To |
|---|---|
| `dim_client.advisor_id` | `dim_advisor.advisor_id` |
| `dim_security.benchmark_id` | `dim_benchmark.benchmark_id` |
| `fact_fees.client_id` | `dim_client.client_id` |
| `fact_fees.advisor_id` | `dim_advisor.advisor_id` |
| `fact_fees.fee_date` | `dim_date.date` |
| `fact_portfolio_snapshot.client_id` | `dim_client.client_id` |
| `fact_portfolio_snapshot.advisor_id` | `dim_advisor.advisor_id` |
| `fact_portfolio_snapshot.benchmark_id` | `dim_benchmark.benchmark_id` |
| `fact_portfolio_snapshot.snapshot_date` | `dim_date.date` |
| `fact_transactions.client_id` | `dim_client.client_id` |
| `fact_transactions.advisor_id` | `dim_advisor.advisor_id` |
| `fact_transactions.security_id` | `dim_security.security_id` (blank on cash transactions) |
| `fact_transactions.txn_date` | `dim_date.date` |

Facts join to `dim_date` on the **date** column (`YYYY-MM-DD`), not on `date_id`.

## 2. Column-type settings for a BI tool

| Type | Columns |
|---|---|
| **Text — must not be converted to numbers** | `dim_client.zip_code` (leading zeros), `dim_client.primary_account_type` and `fact_portfolio_snapshot.account_type` (contain "529"), `dim_advisor.certifications` (contains the real value "None") |
| **Whole number** | all `*_id` columns, `age`, `years_experience`, `aum_target_mm`, `year`, `quarter`, `month`, `week_of_year`, all flag columns |
| **Decimal** | `initial_aum`, `aum`, `aum_basis`, `bps_charged`, `amount`, `shares`, `price`, `expense_ratio_bps`, `return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd`, `cash_pct` |
| **Date (YYYY-MM-DD)** | `client_since`, `date`, `fee_date`, `snapshot_date`, `txn_date` |
| **True/False** | `dim_client.is_active`, `dim_security.is_etf` |

`return_ytd`, `benchmark_return_ytd`, `active_alpha_ytd` and `cash_pct` are decimal fractions (0.0928 = 9.28%). Format them as percentages; do not divide again.

## 3. Flag columns added

| Table | Column | 1 means | Rows = 1 |
|---|---|---|---:|
| `dim_client` | `risk_profile_imputed` | risk_profile was blank and filled with "Balanced" (verified by benchmark 3) | 75 |
| `fact_portfolio_snapshot` | `aum_floor_flag` | aum is exactly $1,000, likely a system floor/placeholder | 420 |
| `fact_portfolio_snapshot` | `return_outlier_flag` | return_ytd is below −60% or above +100% YTD | 2,157 |

Flagged values were **not** changed. Exclude or segment them in reports as needed.

## 4. Known limitations (not fixed)

| Limitation | Reason not fixed |
|---|---|
| 200 transactions (client IDs 2702–3192, $10,888,495.37) were quarantined because their clients are missing from `dim_client` | The clients cannot be identified from this data; the source team should supply them. Transaction totals are understated until then. |
| 7,350 snapshot months have no fee row in `fact_fees` | Could be fee waivers or a missing load; creating fees would invent revenue. |
| Advisory Fee transactions never match `fact_fees` (Advisory) for the same client-month (0 of 7,653) | Different systems with no rule to reconcile them. Use `fact_fees` for fee revenue; do not add the two together. |
| 420 snapshots sit at the $1,000 floor | True balances cannot be recovered; flagged with `aum_floor_flag`. |
| 2,157 snapshots have extreme YTD returns | Internally consistent with benchmark and alpha, so not typos; flagged with `return_outlier_flag`. |
| 75 risk profiles were imputed as "Balanced" | If the source system defaults unknown profiles to benchmark 3, a few may be wrong; flagged with `risk_profile_imputed`. |
| Blank `security_id`, `shares`, `price` on Deposit / Withdrawal / Advisory Fee rows; blank `sector` on ETFs; blank `expense_ratio_bps` on non-ETFs | Legitimate structure, not missing data. Do not fill. |