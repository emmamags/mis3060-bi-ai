# Part B — Decision log
## 1. Defects to fix

### 1a. Duplicate clients with misspelled last names
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `client_id` |
| **Evidence** | 25 clients (IDs 2501–2525) match an existing client on first name, age, city, ZIP, client_since and advisor but have a misspelled last name (e.g. "Taylo" vs "Taylor"), and have no fact rows. |
| **Dimension violated** | Uniqueness |
| **Decision** | Quarantine |
| **Justification** | One real person counted twice inflates client counts and AUM totals by tier/advisor. Keeping the original ID is safe because no fee, snapshot or transaction refers to the duplicates, so no fact row loses its client. |
| **Risk** | If any were genuinely different people, we would drop a real client. Very unlikely: every other field matches and none has any activity. |

### 1b. Transactions for clients that do not exist
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `client_id` |
| **Evidence** | 200 rows reference client IDs that are not in `dim_client`. |
| **Dimension violated** | Referential Integrity |
| **Decision** | Quarantine |
| **Justification** | There is no client, tier, risk profile or advisor to attach them to; any report joining to `dim_client` would silently drop or mis-group them. We cannot guess which real client they belong to. |
| **Risk** | If these are real clients missing from the dimension extract, transaction totals are understated. Documented so the source team can supply the missing clients. |

### 1c. Buy trades with negative share counts
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `shares` |
| **Evidence** | 836 Buy rows have negative shares, yet every one satisfies amount = \|shares\| × price. One is on an orphan transaction quarantined in 1b, so 835 remain to convert. |
| **Dimension violated** | Validity, Accuracy |
| **Decision** | Convert |
| **Justification** | Direction is already carried by `txn_type`; every other Buy has positive shares. The amount and price reconcile to the positive quantity, so the sign is the only thing wrong. |
| **Risk** | If some were actually reversals, we would overstate shares bought. Low: a reversal would also show a negative amount or a Sell type, and none do. |

### 1d. Returns stored as percent text
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `return_ytd` |
| **Evidence** | 300 values are text like "9.28%"; divided by 100, all 300 satisfy return − benchmark = alpha. |
| **Dimension violated** | Validity, Consistency |
| **Decision** | Convert |
| **Justification** | The rest of the column is a decimal fraction (0.0928 = 9.28%). The alpha column independently confirms the correct scale. |
| **Risk** | Low. Converted values carry 4 decimals of precision instead of 6. |

### 1e. State written as full names
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `state` |
| **Evidence** | 78 values are full names (e.g. "Pennsylvania") instead of 2-letter codes. |
| **Dimension violated** | Consistency, Validity |
| **Decision** | Standardize |
| **Justification** | Grouping by state in a BI tool would otherwise split PA into "PA" and "Pennsylvania". Each name maps to exactly one code. |
| **Risk** | None meaningful; the mapping is unambiguous. |

### 1f. Security key stored as decimal text
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `security_id` |
| **Evidence** | 197,175 values are written like "45.0", while `dim_security` uses "45". |
| **Dimension violated** | Consistency, Referential Integrity |
| **Decision** | Convert |
| **Justification** | A relationship on "45.0" vs "45" would match nothing. This is a format issue, not a data issue. |
| **Risk** | None if all values are whole numbers, which the script checks before converting. |

### 1g. Missing risk profile
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `risk_profile` |
| **Evidence** | 76 blanks, one on a duplicate quarantined in 1a, leaving 75; all 75 use benchmark 3, which only Balanced clients use. |
| **Dimension violated** | Completeness |
| **Decision** | Fill |
| **Justification** | The benchmark is assigned from the risk profile, and benchmark 3 maps one-to-one to Balanced, so this is a recovery from another table, not a guess. |
| **Risk** | If the system defaults unknown profiles to benchmark 3, some of these clients may not really be Balanced. A flag column lets analysts exclude them. |

---

## 2. Suspicious values to flag

### 2a. AUM sitting at exactly $1,000
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `aum` |
| **Evidence** | 420 rows (92 clients) sit at exactly $1,000, often between much larger balances. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | Flag |
| **Justification** | Looks like a system floor/placeholder, but the true balance cannot be recovered without inventing it. Flagging lets reports exclude them. |
| **Risk** | If left unflagged, AUM trends dip falsely. If some are real tiny balances, the flag is harmless. |

### 2b. Extreme year-to-date returns
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `return_ytd` |
| **Evidence** | 2,157 rows are outside −60% / +100% YTD, but still satisfy return − benchmark = alpha. |
| **Dimension violated** | Accuracy/Plausibility |
| **Decision** | Flag |
| **Justification** | Internally consistent, so probably a real calculation effect (large deposits into tiny accounts), not a typo. Cannot be fixed without a different return method. |
| **Risk** | Averages of return_ytd would be distorted; reports should use the flag or a median. |

---

## 3. Legitimate structure

### 3a. Blank security, shares and price on cash transactions
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `security_id`, `shares`, `price` |
| **Evidence** | 101,597 blanks, only on Deposit, Withdrawal and Advisory Fee rows. |
| **Dimension violated** | Completeness |
| **Decision** | Leave as is |
| **Justification** | Cash movements have no security, shares or price. |
| **Risk** | None; filling would invent trades. |

### 3b. Blank sector on ETFs
| Field | Entry |
|---|---|
| **Table / column** | `dim_security` / `sector` |
| **Evidence** | 219 blanks, only on ETFs. |
| **Dimension violated** | Completeness |
| **Decision** | Leave as is |
| **Justification** | Funds span sectors. |
| **Risk** | None. |

### 3c. Blank expense ratio on non-ETFs
| Field | Entry |
|---|---|
| **Table / column** | `dim_security` / `expense_ratio_bps` |
| **Evidence** | 281 blanks, only on non-ETFs. |
| **Dimension violated** | Completeness |
| **Decision** | Leave as is |
| **Justification** | Single stocks/bonds have no expense ratio. |
| **Risk** | Filling with 0 would understate fund costs. |

### 3d. "None" in advisor certifications
| Field | Entry |
|---|---|
| **Table / column** | `dim_advisor` / `certifications` |
| **Evidence** | 6 advisors have the text "None". |
| **Dimension violated** | Validity |
| **Decision** | Leave as is |
| **Justification** | Means "no certifications", a real value. |
| **Risk** | A BI tool may read it as null. |

### 3e. "529" as an account type
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `primary_account_type` |
| **Evidence** | 523 clients have "529". |
| **Dimension violated** | Validity |
| **Decision** | Leave as is |
| **Justification** | A 529 college-savings plan, not a number. |
| **Risk** | Must stay text in BI. |

### 3f. Leading zeros in ZIP codes
| Field | Entry |
|---|---|
| **Table / column** | `dim_client` / `zip_code` |
| **Evidence** | ZIPs keep leading zeros (e.g. "02635"). |
| **Dimension violated** | Validity |
| **Decision** | Leave as is |
| **Justification** | Numeric type would drop leading zeros. |
| **Risk** | Must stay text in BI. |

### 3g. Snapshots dated before client_since
| Field | Entry |
|---|---|
| **Table / column** | `fact_portfolio_snapshot` / `snapshot_date` |
| **Evidence** | 930 snapshots predate client_since, all in the join month. |
| **Dimension violated** | Consistency |
| **Decision** | Leave as is |
| **Justification** | Snapshots are dated the 1st of the month. |
| **Risk** | None. |

### 3h. Repeated security names
| Field | Entry |
|---|---|
| **Table / column** | `dim_security` / `name` |
| **Evidence** | 3 names repeat, each with a different ticker. |
| **Dimension violated** | Uniqueness |
| **Decision** | Leave as is |
| **Justification** | Different funds from the same issuer. |
| **Risk** | None; security_id is unique. |

---

## 4. Known limitations

### 4a. Snapshot months with no fee
| Field | Entry |
|---|---|
| **Table / column** | `fact_fees` / `amount` |
| **Evidence** | 7,350 snapshot months have no fee row. |
| **Dimension violated** | Completeness |
| **Decision** | Leave as is |
| **Justification** | Could be waivers; a fee cannot be created without inventing it. |
| **Risk** | Fee revenue may be understated. |

### 4b. Advisory Fee transactions vs fact_fees
| Field | Entry |
|---|---|
| **Table / column** | `fact_transactions` / `amount` |
| **Evidence** | 0 of 7,653 Advisory Fee client-months match `fact_fees`. |
| **Dimension violated** | Consistency |
| **Decision** | Leave as is |
| **Justification** | Different systems; no rule to reconcile them. |
| **Risk** | Don't sum both; use `fact_fees` for fee revenue. |
