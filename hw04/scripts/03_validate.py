"""
HW4 Part D - Referential integrity, rule checks, reconciliations, outliers and a before/after scorecard.

Run from inside the hw04 folder (after 02_clean.py):
    python scripts/03_validate.py

Runs every check on BOTH data/raw and data/clean and saves:
    reports/data_quality_scorecard.csv     one row per table per stage (raw / clean)
    reports/referential_integrity.csv      all 13 relationships, raw and clean
"""

from pathlib import Path

import pandas as pd

HW_DIR = Path(__file__).resolve().parent.parent
STAGES = {"raw": HW_DIR / "data" / "raw", "clean": HW_DIR / "data" / "clean"}
REPORTS = HW_DIR / "reports"
TABLES = ["dim_advisor", "dim_client", "dim_date", "dim_security", "dim_benchmark",
          "fact_fees", "fact_portfolio_snapshot", "fact_transactions"]


def num(s):
    return pd.to_numeric(s, errors="coerce")


def load(folder):
    return {t: pd.read_csv(folder / f"{t}.csv", dtype=str, keep_default_na=False) for t in TABLES}


# ================================================================================================
# 1. Referential integrity - ONE reusable function (keep for Assignment 5)
# ================================================================================================
def _key_text(col, as_numbers):
    """Normalise a key column so blanks/NaN become '' and, if as_numbers, '45.0' and 45 both become '45'."""
    blank = col.isna() | (col.astype(str).str.strip().isin(["", "nan", "NaN", "None"]))
    text = col.astype(str).str.strip()
    if as_numbers:
        v = pd.to_numeric(text, errors="coerce")
        whole = v.notna() & (v % 1 == 0)
        text = text.where(~whole, v[whole].astype("int64").astype(str))
    return text.where(~blank, ""), blank


def orphan_mask(fact_df, fact_key, dim_df, dim_key, as_numbers=False):
    """True for each fact row whose (non-blank) key is not found in the dimension."""
    keys, is_null = _key_text(fact_df[fact_key], as_numbers)
    valid, _ = _key_text(dim_df[dim_key], as_numbers)
    return ~is_null & ~keys.isin(set(valid)), is_null, keys


def check_referential_integrity(fact_df, fact_key, dim_df, dim_key, as_numbers=False):
    """
    Check that every value of fact_df[fact_key] exists in dim_df[dim_key].

    By default keys are compared as stored text, which is how a BI tool joins them, so a
    format mismatch like '45.0' vs '45' counts as an orphan. Pass as_numbers=True to compare
    numeric keys by value instead (use it to tell a format problem from a truly missing key).
    Works whether the tables were read as text or with pandas' default types: blank cells and
    NaN are treated as null keys, not orphans, and keys pandas already parsed as numbers are
    compared by value automatically.

    Returns a dict:
        match_rate           % of non-null keys found in the dimension (None if every key is null)
        orphan_rows          number of non-null rows whose key is not in the dimension
        distinct_orphan_keys number of different orphan key values
        null_key_rate        % of rows where the key is blank/null (None if the table is empty)
    """
    # if pandas already parsed either key as numbers (default read_csv), the text form is
    # meaningless ('45.0'), so compare by value automatically
    if pd.api.types.is_numeric_dtype(fact_df[fact_key]) or pd.api.types.is_numeric_dtype(dim_df[dim_key]):
        as_numbers = True
    orphan, is_null, keys = orphan_mask(fact_df, fact_key, dim_df, dim_key, as_numbers)
    non_null = int((~is_null).sum())
    return {
        "match_rate": round(100 * (non_null - orphan.sum()) / non_null, 3) if non_null else None,
        "orphan_rows": int(orphan.sum()),
        "distinct_orphan_keys": int(keys[orphan].nunique()),
        "null_key_rate": round(100 * is_null.mean(), 3) if len(fact_df) else None,
    }


# (fact/child table, key column, dimension table, dimension key)
RELATIONSHIPS = [
    # ten ID-based relationships
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    # three relationships to the date table
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]


# ================================================================================================
# 2. Column types, keys and business rules (config)
# ================================================================================================
PRIMARY_KEYS = {"dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
                "dim_security": "security_id", "dim_benchmark": "benchmark_id", "fact_fees": "fee_id",
                "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id"}
# extra uniqueness: the table's grain, or (dim_client) the same person entered twice
NATURAL_KEYS = {
    "dim_client": ["first_name", "age", "city", "zip_code", "client_since", "advisor_id", "initial_aum"],
    "dim_date": ["date"],
    "fact_fees": ["client_id", "fee_date", "fee_type"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
}
INT, DATE, BOOL = r"\d+", r"\d{4}-\d{2}-\d{2}", r"True|False"
DEC = r"-?\d+(\.\d+)?([eE][-+]?\d+)?"   # decimals, incl. scientific notation like 9.9e-05
TYPES = {   # expected type of every non-text column; a value "is valid" if it matches the pattern
    "dim_advisor": {"advisor_id": INT, "years_experience": INT, "aum_target_mm": INT},
    "dim_client": {"client_id": INT, "age": INT, "zip_code": r"\d{5}", "initial_aum": DEC,
                   "client_since": DATE, "advisor_id": INT, "is_active": BOOL},
    "dim_date": {"date_id": INT, "date": DATE, "year": INT, "quarter": INT, "month": INT, "week_of_year": INT,
                 "is_month_end": INT, "is_quarter_end": INT, "is_year_end": INT, "is_trading_day": INT},
    "dim_security": {"security_id": INT, "benchmark_id": INT, "is_etf": BOOL, "expense_ratio_bps": DEC},
    "dim_benchmark": {"benchmark_id": INT},
    "fact_fees": {"fee_id": INT, "client_id": INT, "advisor_id": INT, "fee_date": DATE, "aum_basis": DEC,
                  "bps_charged": DEC, "amount": DEC},
    "fact_portfolio_snapshot": {"snapshot_id": INT, "client_id": INT, "advisor_id": INT, "benchmark_id": INT,
                                "snapshot_date": DATE, "year": INT, "month": INT, "aum": DEC, "return_ytd": DEC,
                                "benchmark_return_ytd": DEC, "active_alpha_ytd": DEC, "cash_pct": DEC},
    "fact_transactions": {"txn_id": INT, "client_id": INT, "advisor_id": INT, "security_id": INT,
                          "txn_date": DATE, "shares": DEC, "price": DEC, "amount": DEC},
}
# blanks that are legitimate structure (decision_log 3a-3c): not counted against completeness
STRUCTURAL_BLANKS = {
    ("fact_transactions", "security_id"): lambda d: d.txn_type.isin(["Deposit", "Withdrawal", "Advisory Fee"]),
    ("fact_transactions", "shares"): lambda d: d.txn_type.isin(["Deposit", "Withdrawal", "Advisory Fee"]),
    ("fact_transactions", "price"): lambda d: d.txn_type.isin(["Deposit", "Withdrawal", "Advisory Fee"]),
    ("dim_security", "sector"): lambda d: d.is_etf == "True",
    ("dim_security", "expense_ratio_bps"): lambda d: d.is_etf == "False",
}
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
                "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
ACCOUNT_TYPES = {"Taxable", "IRA", "Roth IRA", "Trust", "529"}


def between(lo=None, hi=None):
    """Rule: blank passes (completeness is checked separately); otherwise the value must be a
    number with lo <= value <= hi. Text that is not a number (e.g. '9.28%') fails."""
    def rule(s):
        v = num(s)
        ok = v.notna()
        if lo is not None:
            ok &= v >= lo
        if hi is not None:
            ok &= v <= hi
        return ok | (s.str.strip() == "")
    return rule


def one_of(values):
    return lambda s: s.isin(values) | (s.str.strip() == "")


# Rule-based checks: every column with a natural business bound, code list or sign rule.
RULES = {
    "dim_advisor": {"years_experience": between(0, 60), "aum_target_mm": between(0.01),
                    "region": one_of({"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West", "Southwest"})},
    "dim_client": {"age": between(18, 110), "initial_aum": between(0.01), "state": one_of(US_STATES),
                   "risk_profile": one_of({"Conservative", "Moderately Conservative", "Balanced",
                                           "Moderately Aggressive", "Aggressive"}),
                   "client_tier": one_of({"Retail", "HNW", "UHNW"}),
                   "primary_account_type": one_of(ACCOUNT_TYPES), "is_active": one_of({"True", "False"})},
    "dim_date": {"quarter": between(1, 4), "month": between(1, 12), "week_of_year": between(1, 53),
                 **{c: one_of({"0", "1"}) for c in ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]}},
    "dim_security": {"asset_class": one_of({"Equity", "Fixed Income", "Alternative", "Cash Equivalent"}),
                     "is_etf": one_of({"True", "False"}), "expense_ratio_bps": between(0, 300)},
    "dim_benchmark": {},
    "fact_fees": {"fee_type": one_of({"Advisory", "Management", "Custodial", "Performance"}),
                  "aum_basis": between(0.01), "bps_charged": between(0, 300), "amount": between(0.01)},
    "fact_portfolio_snapshot": {"aum": between(0.01), "return_ytd": between(-1), "benchmark_return_ytd": between(-1),
                                "cash_pct": between(0, 1), "month": between(1, 12), "year": between(2020, 2024),
                                "account_type": one_of(ACCOUNT_TYPES)},
    "fact_transactions": {"txn_type": one_of({"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"}),
                          "shares": between(0.0001), "price": between(0.01), "amount": between(0.01)},
}


def row_rules(t, d):
    """Rules that compare columns of the same row. Returns {rule name: pass mask}."""
    out = {}
    if t == "fact_transactions":
        trade = d.txn_type.isin(["Buy", "Sell", "Dividend"])
        gap = (num(d.amount) - num(d.shares) * num(d.price)).abs()
        out["amount = shares x price"] = ~trade | (gap <= 0.05)
    if t == "fact_fees":
        calc = num(d.aum_basis) * num(d.bps_charged) / 10000 / 12
        out["amount = aum x bps / 10000 / 12"] = (num(d.amount) - calc).abs() <= 0.05
    if t == "fact_portfolio_snapshot":
        alpha = (num(d.return_ytd) - num(d.benchmark_return_ytd) - num(d.active_alpha_ytd)).abs()
        out["alpha = return - benchmark"] = alpha <= 0.0001
    return out


# ================================================================================================
# 3. Cross-table reconciliations
# ================================================================================================
def reconciliations(T):
    s, f, c, tx = T["fact_portfolio_snapshot"], T["fact_fees"], T["dim_client"], T["fact_transactions"]
    out = []
    # R1: the AUM a fee was charged on should equal that client's AUM in the snapshot for the same month
    j = f.merge(s[["client_id", "snapshot_date", "aum"]], left_on=["client_id", "fee_date"],
                right_on=["client_id", "snapshot_date"], how="left")
    ok = (num(j.aum_basis) - num(j.aum)).abs() <= 0.01
    out.append(("R1 fact_fees.aum_basis = snapshot aum (same client-month)", ok.sum(), len(j)))
    # R2: recomputed fee (aum_basis x bps / 10000 / 12) vs the stored fee amount
    calc = num(f.aum_basis) * num(f.bps_charged) / 10000 / 12
    ok = (num(f.amount) - calc).abs() <= 0.05
    out.append(("R2 recomputed fee = stored fee amount", ok.sum(), len(f)))
    # R3: snapshot account type should be the client's primary account type
    j = s.merge(c[["client_id", "primary_account_type"]], on="client_id", how="left")
    ok = j.account_type == j.primary_account_type
    out.append(("R3 snapshot account_type = dim_client.primary_account_type", ok.sum(), len(j)))
    # R4: the advisor on every transaction should be the client's advisor in dim_client
    j = tx.merge(c[["client_id", "advisor_id"]], on="client_id", how="left", suffixes=("", "_dim"))
    ok = j.advisor_id == j.advisor_id_dim
    out.append(("R4 transaction advisor = client's advisor", ok.sum(), len(j)))
    # R5: Advisory Fee transactions vs fact_fees (Advisory), same client-month - known limitation 4b
    a = tx[tx.txn_type == "Advisory Fee"].assign(m=lambda d: d.txn_date.str[:7], v=lambda d: num(d.amount))
    b = f[f.fee_type == "Advisory"].assign(m=lambda d: d.fee_date.str[:7], v=lambda d: num(d.amount))
    g = pd.concat([a.groupby(["client_id", "m"]).v.sum().rename("tx"),
                   b.groupby(["client_id", "m"]).v.sum().rename("fee")], axis=1).dropna()
    out.append(("R5 Advisory Fee txns = fact_fees Advisory (client-months in both)",
                ((g.tx - g.fee).abs() <= 0.01).sum(), len(g)))
    return out


# ================================================================================================
# 4. IQR outliers on columns with no natural upper bound
# ================================================================================================
IQR_COLUMNS = [("fact_transactions", "amount"), ("fact_portfolio_snapshot", "aum"),
               ("fact_fees", "amount"), ("dim_client", "initial_aum")]


def iqr_flags(s):
    v = num(s)
    q1, q3 = v.quantile(0.25), v.quantile(0.75)
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    return (v < lo) | (v > hi), lo, hi


# ================================================================================================
# 5. Scorecard
# ================================================================================================
RAW_COLUMNS = {}   # filled in main(): the raw column list of each table


def scorecard_row(stage, t, T):
    d = T[t]
    # completeness: non-blank cells, ignoring blanks that are legitimate structure
    expected = blank = 0
    for col in RAW_COLUMNS[t]:          # same columns in both stages (added flag columns excluded)
        b = d[col].str.strip() == ""
        if (t, col) in STRUCTURAL_BLANKS:
            b = b & ~STRUCTURAL_BLANKS[(t, col)](d)
            expected += int((~STRUCTURAL_BLANKS[(t, col)](d)).sum())
        else:
            expected += len(d)
        blank += int(b.sum())
    # key uniqueness: rows that are not an extra copy on the primary key or the natural key
    extra = d[PRIMARY_KEYS[t]].duplicated()
    if t in NATURAL_KEYS:
        extra |= d.duplicated(NATURAL_KEYS[t])
    # type validity: non-blank values in typed columns that match the expected pattern
    cells = valid = 0
    for col, pattern in TYPES[t].items():
        s = d[col][d[col].str.strip() != ""]
        cells += len(s)
        ok_pattern = s.str.fullmatch(pattern)
        if pattern == DATE:   # format AND a real calendar date (2023-02-30 fails)
            ok_pattern &= pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").notna()
        valid += int(ok_pattern.sum())
    # rule pass: rows that pass every column rule and every row rule
    ok = pd.Series(True, index=d.index)
    for col, rule in RULES[t].items():
        ok &= rule(d[col])
    for mask in row_rules(t, d).values():
        ok &= mask
    # referential match: % of rows whose non-blank foreign keys ALL exist in their dimensions
    rels = [r for r in RELATIONSHIPS if r[0] == t]
    if rels:
        all_match = pd.Series(True, index=d.index)
        for child, ckey, parent, pkey in rels:
            all_match &= ~orphan_mask(d, ckey, T[parent], pkey)[0]
        ref = round(100 * all_match.mean(), 3)
    else:
        ref = None                      # left blank in the csv: this table has no foreign keys
    return {
        "table": t, "stage": stage, "rows": len(d),
        "pct_completeness": round(100 * (1 - blank / expected), 3),
        "pct_key_uniqueness": round(100 * (1 - extra.mean()), 3),
        "pct_type_validity": round(100 * valid / cells, 3) if cells else 100.0,
        "pct_rule_pass": round(100 * ok.mean(), 3),
        "pct_referential_match": ref,
    }


def main():
    REPORTS.mkdir(exist_ok=True)
    data = {stage: load(folder) for stage, folder in STAGES.items()}
    RAW_COLUMNS.update({t: list(df.columns) for t, df in data["raw"].items()})
    pd.set_option("display.width", 220, "display.max_columns", 20, "display.max_colwidth", 70)

    # ---- referential integrity on every relationship, both stages ----
    print("=" * 100 + "\nREFERENTIAL INTEGRITY (13 relationships)\n" + "=" * 100)
    ri_rows = []
    for stage, T in data.items():
        for child, ckey, parent, pkey in RELATIONSHIPS:
            r = check_referential_integrity(T[child], ckey, T[parent], pkey)
            r_num = check_referential_integrity(T[child], ckey, T[parent], pkey, as_numbers=True)
            ri_rows.append({"stage": stage, "child_table": child, "child_key": ckey,
                            "parent_table": parent, "parent_key": pkey, **r,
                            "match_rate_as_numbers": r_num["match_rate"]})
    ri = pd.DataFrame(ri_rows)
    wide = ri.set_index(["child_table", "child_key", "parent_table", "stage"])[
        ["match_rate", "match_rate_as_numbers", "orphan_rows", "distinct_orphan_keys", "null_key_rate"]].unstack("stage")
    wide = wide.reindex(columns=["raw", "clean"], level="stage")
    print(wide.to_string())
    print("  match_rate compares keys as stored text (how a BI tool joins); match_rate_as_numbers compares values.\n"
          "  Raw security_id: 0% as text but 100% as numbers -> a format problem ('45.0' vs '45'), not missing securities.")
    ri.to_csv(REPORTS / "referential_integrity.csv", index=False)

    # ---- rule checks ----
    print("\n" + "=" * 100 + "\nRULE CHECKS (rows failing each rule)\n" + "=" * 100)
    for t in TABLES:
        checks = {**{f"{c}": r for c, r in RULES[t].items()}}
        lines = []
        for name, rule in checks.items():
            fails = {stage: int((~rule(data[stage][t][name])).sum()) for stage in data}
            if fails["raw"] or fails["clean"]:
                lines.append(f"    {name:34} raw {fails['raw']:>6}   clean {fails['clean']:>6}")
        for name in row_rules(t, data["raw"][t]):
            fails = {stage: int((~row_rules(t, data[stage][t])[name]).sum()) for stage in data}
            lines.append(f"    {name:34} raw {fails['raw']:>6}   clean {fails['clean']:>6}")
        n_rules = len(RULES[t]) + len(row_rules(t, data["raw"][t]))
        print(f"  {t} ({n_rules} rules)" + ("" if lines else ": all pass in both stages"))
        print("\n".join(lines)) if lines else None

    # ---- cross-table reconciliations ----
    print("\n" + "=" * 100 + "\nCROSS-TABLE RECONCILIATIONS (rows that agree / rows compared)\n" + "=" * 100)
    rec = {stage: reconciliations(T) for stage, T in data.items()}
    for (name, ok_r, n_r), (_, ok_c, n_c) in zip(rec["raw"], rec["clean"]):
        pct = lambda ok, n: f"{100*ok/n:6.2f}%" if n else "   n/a"
        print(f"  {name:66} raw {ok_r:>7,}/{n_r:<7,} ({pct(ok_r, n_r)})   clean {ok_c:>7,}/{n_c:<7,} ({pct(ok_c, n_c)})")

    # ---- IQR outliers ----
    print("\n" + "=" * 100 + "\nIQR OUTLIERS (outside Q1 - 1.5*IQR .. Q3 + 1.5*IQR), clean data\n" + "=" * 100)
    for t, col in IQR_COLUMNS:
        flags, lo, hi = iqr_flags(data["clean"][t][col])
        print(f"  {t + '.' + col:36} {flags.sum():>7,} of {len(flags):>7,} flagged ({100*flags.mean():5.2f}%)   "
              f"fence {lo:,.2f} .. {hi:,.2f}")
    print("  Flagged does not mean wrong: these columns are right-skewed (a few very large accounts and trades),\n"
          "  so the IQR fence flags real high-net-worth activity; a flag is a prompt to look, not proof of an error.")

    # ---- scorecard ----
    print("\n" + "=" * 100 + "\nDATA QUALITY SCORECARD\n" + "=" * 100)
    card = pd.DataFrame([scorecard_row(stage, t, data[stage]) for t in TABLES for stage in data])
    print(card.to_string(index=False))
    card.to_csv(REPORTS / "data_quality_scorecard.csv", index=False)
    print(f"\nSaved {REPORTS / 'data_quality_scorecard.csv'} and {REPORTS / 'referential_integrity.csv'}")


if __name__ == "__main__":
    main()
    