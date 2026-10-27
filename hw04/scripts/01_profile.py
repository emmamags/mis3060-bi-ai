"""
HW4 Part A - Generic data-quality profiler for the Wildcat Capital tables.

How to run (from inside the hw04 folder):
    python scripts/01_profile.py                     # profiles data/raw -> reports/*_raw.csv
    python scripts/01_profile.py --data data/clean --stage clean   # re-run on cleaned data later

Design
------
* Every file is read as TEXT (dtype=str, keep_default_na=False) so nothing is silently converted.
* PART 1 (profile_column) is fully generic: it knows nothing about any table. It infers each
  column's expected type from what most values look like, then reports what does NOT fit.
* PART 2 (the RULES / KEYS config) holds the business knowledge: primary keys, foreign keys,
  allowed values and ranges. The check functions that read the config are generic too, so a
  new table only needs a config entry, not new code.
* Every finding is tagged ERROR / WARN / INFO and saved to reports/dq_summary_<stage>.csv.
"""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------------------------
HW_DIR = Path(__file__).resolve().parent.parent          # .../hw04
TABLE_FILES = [
    "dim_advisor.csv", "dim_client.csv", "dim_date.csv", "dim_security.csv", "dim_benchmark.csv",
    "fact_fees.csv", "fact_portfolio_snapshot.csv", "fact_transactions.csv",
]
NULL_TOKENS = {"none", "null", "nan", "na", "n/a", "-", "?"}   # text that often *means* missing
PARSE_THRESHOLD = 0.90   # a column "is" a type if >= 90% of its non-blank values parse as it

findings = []            # every check appends one dict here -> dq_summary csv


def add_finding(severity, group, table, column, check, rows, total, example="", detail=""):
    """Record one data-quality finding."""
    findings.append({
        "severity": severity, "check_group": group, "table": table, "column": column,
        "check": check, "rows_affected": int(rows),
        "pct_rows": round(100 * rows / total, 3) if total else 0.0,
        "example": str(example)[:120], "detail": detail,
    })


# ----------------------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------------------
def load_tables(data_dir):
    tables = {}
    for fname in TABLE_FILES:
        path = data_dir / fname
        if not path.exists():
            print(f"  !! MISSING FILE: {path} (skipped)")
            add_finding("ERROR", "0 Load", fname.replace(".csv", ""), "", "file missing", 0, 0,
                        detail=str(path))
            continue
        tables[fname.replace(".csv", "")] = pd.read_csv(path, dtype=str, keep_default_na=False)
    return tables


# ----------------------------------------------------------------------------------------------
# PART 1 - generic column profile
# ----------------------------------------------------------------------------------------------
def value_shape(v):
    """'03897' -> '99999', 'Roth IRA' -> 'Aaaa AAA'... digits->9, letters->A, rest kept."""
    return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", v))


def parse_share(s):
    """For each candidate type, the share of non-blank values that parse as that type."""
    if len(s) == 0:
        return {}
    num = pd.to_numeric(s, errors="coerce")
    is_int = s.str.fullmatch(r"[+-]?\d+")
    date = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    boolean = s.str.lower().isin({"true", "false", "0", "1", "yes", "no"})
    return {
        "bool": boolean.mean() if s.nunique() <= 2 else 0.0,
        "integer": is_int.mean(),
        "decimal": num.notna().mean(),
        "date": date.notna().mean(),
    }


def infer_type(shares):
    """Pick the most specific type that >= PARSE_THRESHOLD of values satisfy."""
    for t in ["bool", "date", "integer", "decimal"]:
        if shares.get(t, 0) >= PARSE_THRESHOLD:
            return t
    return "text"


def parse_fails(s, typ):
    """Boolean mask of non-blank values that do NOT parse as the inferred type."""
    if typ == "integer":
        return ~s.str.fullmatch(r"[+-]?\d+")
    if typ == "decimal":
        return pd.to_numeric(s, errors="coerce").isna()
    if typ == "date":
        return pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").isna()
    if typ == "bool":
        return ~s.str.lower().isin({"true", "false", "0", "1", "yes", "no"})
    return pd.Series(False, index=s.index)


def profile_column(table, col, raw):
    n = len(raw)
    stripped = raw.str.strip()
    blank = stripped == ""
    nonblank = raw[~blank]
    null_tok = stripped.str.lower().isin(NULL_TOKENS)

    shares = parse_share(nonblank[~null_tok[~blank]])
    typ = infer_type(shares)
    fails = parse_fails(nonblank, typ) & ~null_tok[~blank]

    shapes = nonblank.map(value_shape).value_counts()
    lead_trail = (raw != stripped) & ~blank
    double_sp = raw.str.contains(r"\s{2,}", regex=True)
    # values that are the same after trimming + lower-casing but are written differently
    norm = nonblank.str.strip().str.lower()
    case_variants = int((nonblank.groupby(norm).nunique() > 1).sum())

    num = pd.to_numeric(nonblank, errors="coerce")
    row = {
        "table": table, "column": col, "rows": n,
        "blank_count": int(blank.sum()), "blank_pct": round(100 * blank.mean(), 3),
        "null_token_count": int(null_tok.sum()),
        "distinct": int(raw.nunique()),
        "inferred_type": typ,
        "parse_fail_count": int(fails.sum()),
        "parse_fail_pct": round(100 * fails.sum() / max(len(nonblank), 1), 3),
        "parse_fail_examples": "; ".join(nonblank[fails].unique()[:5]),
        "n_shapes": int(len(shapes)),
        "top_shapes": "; ".join(f"{k} ({v})" for k, v in shapes.head(4).items()),
        "lead_trail_ws": int(lead_trail.sum()),
        "double_space": int(double_sp.sum()),
        "case_or_space_variants": case_variants,
        "min": num.min() if typ in ("integer", "decimal") else (nonblank.min() if typ == "date" and len(nonblank) else ""),
        "max": num.max() if typ in ("integer", "decimal") else (nonblank.max() if typ == "date" and len(nonblank) else ""),
        "top_values": "; ".join(f"{k} ({v})" for k, v in raw.value_counts().head(5).items()),
    }

    # ---- column-level findings that need no business knowledge ----
    G = "1 Column"
    if row["parse_fail_count"]:
        add_finding("ERROR", G, table, col, f"values fail to parse as {typ}", row["parse_fail_count"], n,
                    row["parse_fail_examples"], "will become NaN / break math if converted blindly")
    if row["blank_count"]:
        add_finding("WARN", G, table, col, "blank values", row["blank_count"], n,
                    detail="see 2 Row 'structural blank' check: may be legitimate")
    if row["null_token_count"]:
        add_finding("INFO", G, table, col, "text that looks like a null token", row["null_token_count"], n,
                    raw[null_tok].iloc[0], "pd.read_csv default would turn this into NaN - decide if it means 'missing' or a real value")
    if row["lead_trail_ws"] or row["double_space"]:
        add_finding("WARN", G, table, col, "whitespace problems", row["lead_trail_ws"] + row["double_space"], n)
    if case_variants:
        add_finding("WARN", G, table, col, "same value written different ways (case/space)", case_variants, n)
    # integer keys stored as '45.0'
    if col.endswith("_id") and typ == "decimal" and len(num.dropna()) and (num.dropna() % 1 == 0).all():
        add_finding("ERROR", G, table, col, "integer key stored as decimal text (e.g. '45.0')",
                    int(nonblank.str.contains(r"\.").sum()), n, nonblank.iloc[0],
                    "text join to an integer PK ('45') will fail")
    # mixed formats in a code-like column: one shape dominates, a few values look different
    if typ == "text" and row["distinct"] >= 5 and len(shapes) > 1 and shapes.iloc[0] / len(nonblank) >= 0.90:
        odd = nonblank[nonblank.map(value_shape) != shapes.index[0]]
        add_finding("WARN", G, table, col, f"mixed formats: {round(100*shapes.iloc[0]/len(nonblank),1)}% look like '{shapes.index[0]}'",
                    len(odd), n, "; ".join(odd.unique()[:6]))
    return row, typ


# ----------------------------------------------------------------------------------------------
# PART 2 - business knowledge (config).  Generic functions below read these.
# ----------------------------------------------------------------------------------------------
PRIMARY_KEYS = {
    "dim_advisor": "advisor_id", "dim_client": "client_id", "dim_date": "date_id",
    "dim_security": "security_id", "dim_benchmark": "benchmark_id",
    "fact_fees": "fee_id", "fact_portfolio_snapshot": "snapshot_id", "fact_transactions": "txn_id",
}
NATURAL_KEYS = {          # combinations that should also be unique (grain of the table)
    "dim_date": ["date"],
    "fact_fees": ["client_id", "fee_date", "fee_type"],
    "fact_portfolio_snapshot": ["client_id", "snapshot_date"],
}
# (child table, child column, parent table, parent column)
FOREIGN_KEYS = [
    ("dim_client", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_fees", "client_id", "dim_client", "client_id"),
    ("fact_fees", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "client_id", "dim_client", "client_id"),
    ("fact_portfolio_snapshot", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_portfolio_snapshot", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_transactions", "client_id", "dim_client", "client_id"),
    ("fact_transactions", "advisor_id", "dim_advisor", "advisor_id"),
    ("fact_transactions", "security_id", "dim_security", "security_id"),
    ("dim_security", "benchmark_id", "dim_benchmark", "benchmark_id"),
    ("fact_fees", "fee_date", "dim_date", "date"),
    ("fact_portfolio_snapshot", "snapshot_date", "dim_date", "date"),
    ("fact_transactions", "txn_date", "dim_date", "date"),
]
US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
                "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
ALLOWED = {
    ("dim_client", "state"): US_STATES,
    ("dim_client", "risk_profile"): {"Conservative", "Moderately Conservative", "Balanced",
                                     "Moderately Aggressive", "Aggressive"},
    ("dim_client", "client_tier"): {"Retail", "HNW", "UHNW"},
    ("dim_client", "primary_account_type"): {"Taxable", "IRA", "Roth IRA", "Trust", "529"},
    ("dim_client", "is_active"): {"True", "False"},
    ("dim_advisor", "region"): {"Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West", "Southwest"},
    ("fact_portfolio_snapshot", "account_type"): {"Taxable", "IRA", "Roth IRA", "Trust", "529"},
    ("fact_fees", "fee_type"): {"Advisory", "Management", "Custodial", "Performance"},
    ("dim_security", "asset_class"): {"Equity", "Fixed Income", "Alternative", "Cash Equivalent"},
    ("dim_security", "is_etf"): {"True", "False"},
    ("fact_transactions", "txn_type"): {"Buy", "Sell", "Dividend", "Deposit", "Withdrawal", "Advisory Fee"},
    **{("dim_date", c): {"0", "1"} for c in ["is_month_end", "is_quarter_end", "is_year_end", "is_trading_day"]},
}
RANGES = {   # (min, max) inclusive; None = no bound.  Natural business bounds only.
    ("dim_client", "age"): (18, 110),
    ("dim_client", "initial_aum"): (0.01, None),
    ("dim_advisor", "years_experience"): (0, 60),
    ("dim_advisor", "aum_target_mm"): (0.01, None),
    ("dim_security", "expense_ratio_bps"): (0, 300),
    ("fact_fees", "aum_basis"): (0.01, None),
    ("fact_fees", "bps_charged"): (0, 300),
    ("fact_fees", "amount"): (0.01, None),
    ("fact_portfolio_snapshot", "aum"): (0.01, None),
    ("fact_portfolio_snapshot", "cash_pct"): (0, 1),
    ("fact_portfolio_snapshot", "return_ytd"): (-1, None),          # can't lose more than 100%
    ("fact_portfolio_snapshot", "benchmark_return_ytd"): (-1, None),
    ("fact_portfolio_snapshot", "month"): (1, 12),
    ("fact_transactions", "shares"): (0.0001, None),                 # sign is carried by txn_type
    ("fact_transactions", "price"): (0.01, None),
    ("fact_transactions", "amount"): (0.01, None),
}
PLAUSIBLE = {  # not hard limits, but values outside these deserve a look (WARN, not ERROR)
    ("fact_portfolio_snapshot", "return_ytd"): (-0.6, 1.0),     # beyond -60% / +100% in one year
    ("fact_transactions", "amount"): (None, 1_000_000),
}


def num(s):
    return pd.to_numeric(s, errors="coerce")


# ---------------- Group 1: column level (keys, allowed values, ranges) ----------------
def check_column_rules(T):
    G = "1 Column"
    for t, pk in PRIMARY_KEYS.items():
        if t not in T:
            continue
        df = T[t]
        dup = df[pk].duplicated(keep=False)
        sev = "ERROR" if dup.any() else "INFO"
        add_finding(sev, G, t, pk, "primary key unique", dup.sum(), len(df),
                    df.loc[dup, pk].head(1).tolist(), f"{df[pk].nunique()} distinct of {len(df)} rows")
    for (t, c), allowed in ALLOWED.items():
        if t not in T:
            continue
        s = T[t][c]
        bad = ~s.isin(allowed) & (s.str.strip() != "")
        if bad.any():
            add_finding("ERROR", G, t, c, "value not in allowed list", bad.sum(), len(s),
                        "; ".join(s[bad].value_counts().head(6).index), f"allowed: {sorted(allowed)}")
    for (t, c), (lo, hi) in RANGES.items():
        if t not in T:
            continue
        v = num(T[t][c])
        bad = ((v < lo) if lo is not None else False) | ((v > hi) if hi is not None else False)
        bad = pd.Series(bad, index=v.index).fillna(False)
        if bad.any():
            add_finding("ERROR", G, t, c, f"outside business range [{lo}, {hi}]", bad.sum(), len(v),
                        "; ".join(T[t].loc[bad, c].head(5)), f"observed min {v.min()} max {v.max()}")
    for (t, c), (lo, hi) in PLAUSIBLE.items():
        if t not in T:
            continue
        raw = T[t][c].str.strip()
        v = num(raw.str.rstrip("%"))
        v = v.where(~raw.str.endswith("%"), v / 100)   # "9.28%" -> 0.0928
        bad = pd.Series(((v < lo) if lo is not None else False) | ((v > hi) if hi is not None else False),
                        index=v.index).fillna(False)
        if bad.any():
            add_finding("WARN", "1 Column", t, c, f"implausible (outside [{lo}, {hi}])", bad.sum(), len(v),
                        "; ".join(T[t].loc[bad, c].head(5)), "investigate - may be real (tiny accounts, big flows)")


# ---------------- Group 2: single-table rules ----------------
def check_structural_blanks(t, df):
    """Is a column blank ONLY for certain values of a low-cardinality column? -> legitimate structure."""
    for col in df.columns:
        blank = df[col].str.strip() == ""
        if not blank.any():
            continue
        explained = False
        for other in df.columns:
            if other == col or df[other].nunique() > 12:
                continue
            rate = blank.groupby(df[other]).mean()
            if set(rate.round(6).unique()) <= {0.0, 1.0}:
                cats = sorted(rate[rate == 1].index)
                add_finding("INFO", "2 Row", t, col, f"structural blank: blank exactly when {other} in {cats}",
                            blank.sum(), len(df), detail="legitimate structure, not a defect")
                explained = True
                break
        if not explained:
            add_finding("WARN", "2 Row", t, col, "blank not explained by any category column (true missing?)",
                        blank.sum(), len(df))


def check_duplicates(t, df):
    G = "2 Row"
    pk = PRIMARY_KEYS.get(t)
    body = df.drop(columns=[pk]) if pk in df else df
    d = body.duplicated(keep=False)
    add_finding("ERROR" if d.any() else "INFO", G, t, "(all but PK)", "exact duplicate rows ignoring the ID",
                d.sum(), len(df))
    if t in NATURAL_KEYS:
        k = NATURAL_KEYS[t]
        d = df.duplicated(k, keep=False)
        add_finding("ERROR" if d.any() else "INFO", G, t, "+".join(k), "natural key (grain) unique", d.sum(), len(df))


def check_client_near_duplicates(T):
    """Same person entered twice with a slightly different spelling: match on everything except the name."""
    if "dim_client" not in T:
        return
    c = T["dim_client"]
    key = ["first_name", "age", "city", "zip_code", "client_since", "advisor_id"]
    grp = c[c.duplicated(key, keep=False)].sort_values(key)
    if len(grp):
        ex = grp.groupby(key).last_name.apply(lambda s: " vs ".join(s)).head(3).tolist()
        add_finding("ERROR", "2 Row", "dim_client", "+".join(key),
                    "near-duplicate clients (same person, different last-name spelling)",
                    grp.client_id.nunique() // 2, len(c), "; ".join(ex),
                    "pairs match on first name, age, city, zip, client_since, advisor")


def check_row_contradictions(T):
    G = "2 Row"
    if "fact_transactions" in T:
        x = T["fact_transactions"]
        sh, pr, am = num(x.shares), num(x.price), num(x.amount)
        trade = x.txn_type.isin(["Buy", "Sell"])
        diff = (am - sh * pr).abs()
        bad = trade & (diff > 0.05)
        add_finding("ERROR" if bad.any() else "INFO", G, "fact_transactions", "amount vs shares*price",
                    "Buy/Sell amount = shares x price (+-0.05)", bad.sum(), len(x),
                    x.loc[bad, ["txn_id", "shares", "price", "amount"]].head(2).values.tolist())
        div = x.txn_type == "Dividend"
        dbad = div & (diff > 0.05)
        add_finding("ERROR" if dbad.any() else "INFO", G, "fact_transactions", "amount vs shares*price",
                    "Dividend amount = shares x price (+-0.05)", dbad.sum(), len(x))
        fix = bad & ((am - sh.abs() * pr).abs() <= 0.05)
        if fix.any():
            add_finding("WARN", G, "fact_transactions", "shares", "...of those, amount = |shares| x price (sign flipped)",
                        fix.sum(), len(x), detail="evidence the amount is right and only the sign of shares is wrong")
    if "fact_fees" in T:
        f = T["fact_fees"]
        calc = num(f.aum_basis) * num(f.bps_charged) / 10000 / 12
        bad = (num(f.amount) - calc).abs() > 0.05
        add_finding("ERROR" if bad.any() else "INFO", G, "fact_fees", "amount", "amount = aum_basis x bps/10000/12 (+-0.05)",
                    bad.sum(), len(f))
    if "fact_portfolio_snapshot" in T:
        s = T["fact_portfolio_snapshot"]
        ret = num(s.return_ytd.str.rstrip("%"))
        ret = np.where(s.return_ytd.str.endswith("%"), ret / 100, ret)
        bad = (pd.Series(ret, index=s.index) - num(s.benchmark_return_ytd) - num(s.active_alpha_ytd)).abs() > 1e-4
        add_finding("ERROR" if bad.any() else "INFO", G, "fact_portfolio_snapshot", "active_alpha_ytd",
                    "alpha = return_ytd - benchmark_return_ytd (treating 'x%' as x/100)", bad.sum(), len(s))
        bad = (s.snapshot_date.str[:4] != s.year) | (num(s.snapshot_date.str[5:7]) != num(s.month))
        add_finding("ERROR" if bad.any() else "INFO", G, "fact_portfolio_snapshot", "year/month",
                    "year & month agree with snapshot_date", bad.sum(), len(s))
        floor = num(s.aum) == num(s.aum).min()
        if floor.sum() > 10:
            add_finding("WARN", G, "fact_portfolio_snapshot", "aum",
                        f"{floor.sum()} rows sit exactly at the minimum value {num(s.aum).min()} (floor/placeholder?)",
                        floor.sum(), len(s), detail=f"{s.loc[floor,'client_id'].nunique()} clients")
    if "dim_date" in T:
        d = T["dim_date"]
        dt = pd.to_datetime(d.date, errors="coerce")
        checks = {
            "year": dt.dt.year.astype("Int64").astype(str), "quarter": dt.dt.quarter.astype("Int64").astype(str),
            "month": dt.dt.month.astype("Int64").astype(str), "day_of_week": dt.dt.day_name(),
            "month_name": dt.dt.month_name(),
            "is_month_end": dt.dt.is_month_end.astype(int).astype(str),
            "is_quarter_end": dt.dt.is_quarter_end.astype(int).astype(str),
            "is_year_end": dt.dt.is_year_end.astype(int).astype(str),
            "is_trading_day": (dt.dt.dayofweek < 5).astype(int).astype(str),
        }
        for c, expect in checks.items():
            bad = d[c] != expect
            add_finding("ERROR" if bad.any() else "INFO", G, "dim_date", c, f"{c} agrees with date", bad.sum(), len(d),
                        detail="is_trading_day check = weekday only (holidays ignored)" if c == "is_trading_day" else "")


# ---------------- Group 3: referential integrity ----------------
def check_referential_integrity(T):
    for child, ccol, parent, pcol in FOREIGN_KEYS:
        if child not in T or parent not in T:
            add_finding("WARN", "3 RI", child, ccol, f"-> {parent}.{pcol} NOT CHECKED (table missing)", 0, 0)
            continue
        fk = T[child][ccol]
        nonnull = fk.str.strip() != ""
        # compare as numbers when both sides are numeric so '45.0' vs '45' is a FORMAT issue, not an orphan
        pk_vals = T[parent][pcol]
        if num(fk[nonnull]).notna().all() and num(pk_vals).notna().all() and not ccol.endswith("date"):
            orphan = nonnull & ~num(fk).isin(set(num(pk_vals)))
        else:
            orphan = nonnull & ~fk.isin(set(pk_vals))
        add_finding("ERROR" if orphan.any() else "INFO", "3 RI", child, ccol,
                    f"FK -> {parent}.{pcol}: orphan rows", orphan.sum(), len(fk),
                    "; ".join(fk[orphan].unique()[:5]),
                    f"{fk[orphan].nunique()} distinct orphan keys; null-key rows {(~nonnull).sum()}")


# ---------------- Group 4: cross-table business rules ----------------
def check_cross_table(T):
    G = "4 Cross"
    c = T.get("dim_client")
    if c is None:
        return
    for ft, dcol in [("fact_fees", "fee_date"), ("fact_portfolio_snapshot", "snapshot_date"), ("fact_transactions", "txn_date")]:
        if ft not in T:
            continue
        m = T[ft].merge(c[["client_id", "advisor_id", "client_since", "primary_account_type"]],
                        on="client_id", how="inner", suffixes=("", "_dim"))
        bad = m.advisor_id != m.advisor_id_dim
        add_finding("ERROR" if bad.any() else "INFO", G, ft, "advisor_id", "fact advisor = client's advisor in dim_client",
                    bad.sum(), len(m))
        early = m[dcol] < m.client_since
        if early.any():
            same_month = (m.loc[early, dcol].str[:7] == m.loc[early, "client_since"].str[:7]).mean()
            sev = "INFO" if same_month == 1 else "ERROR"
            add_finding(sev, G, ft, dcol, "activity dated before client_since", early.sum(), len(m),
                        detail=f"{same_month:.0%} fall in the same month the client joined "
                               "(month-start snapshot convention -> legitimate)" if same_month == 1 else "")
    if "fact_portfolio_snapshot" in T:
        s = T["fact_portfolio_snapshot"]
        m = s.merge(c[["client_id", "primary_account_type", "risk_profile"]], on="client_id")
        bad = m.account_type != m.primary_account_type
        add_finding("ERROR" if bad.any() else "INFO", G, "fact_portfolio_snapshot", "account_type",
                    "snapshot account_type = dim_client.primary_account_type", bad.sum(), len(m))
        # does each risk profile map to exactly one benchmark?  (lets us test a fill for blanks)
        xt = pd.crosstab(m.risk_profile.replace("", "(blank)"), m.benchmark_id)
        mapping = "; ".join(f"{rp}->{'/'.join(xt.columns[xt.loc[rp] > 0])}" for rp in xt.index)
        add_finding("INFO", G, "fact_portfolio_snapshot", "benchmark_id", "risk_profile -> benchmark mapping",
                    0, len(m), detail=mapping)
        if "fact_fees" in T:
            f = T["fact_fees"]
            j = f.merge(s[["client_id", "snapshot_date", "aum"]], left_on=["client_id", "fee_date"],
                        right_on=["client_id", "snapshot_date"], how="left")
            bad = j.aum.isna() | ((num(j.aum_basis) - num(j.aum)).abs() > 0.01)
            add_finding("ERROR" if bad.any() else "INFO", G, "fact_fees", "aum_basis",
                        "fee aum_basis = snapshot aum for same client-month", bad.sum(), len(f))
            k = s.merge(f[["client_id", "fee_date"]].drop_duplicates(), left_on=["client_id", "snapshot_date"],
                        right_on=["client_id", "fee_date"], how="left")
            miss = k.fee_date.isna()
            add_finding("WARN" if miss.any() else "INFO", G, "fact_portfolio_snapshot", "(fees)",
                        "snapshot month with no fee charged", miss.sum(), len(s),
                        detail=f"{k.loc[miss,'client_id'].nunique()} clients - waiver or missing load?")
        if "fact_transactions" in T:
            tx = T["fact_transactions"]
            a = tx[tx.txn_type == "Advisory Fee"].assign(m=lambda d: d.txn_date.str[:7], a=lambda d: num(d.amount))
            if "fact_fees" in T:
                ff = T["fact_fees"][T["fact_fees"].fee_type == "Advisory"].assign(m=lambda d: d.fee_date.str[:7], a=lambda d: num(d.amount))
                g = pd.concat([a.groupby(["client_id", "m"]).a.sum().rename("tx"),
                               ff.groupby(["client_id", "m"]).a.sum().rename("fee")], axis=1).dropna()
                match = ((g.tx - g.fee).abs() < 0.01).sum()
                add_finding("WARN", G, "fact_transactions", "amount (Advisory Fee)",
                            "Advisory Fee debits vs fact_fees (Advisory only), same client-month", len(g) - match, len(g),
                            detail=f"{match} of {len(g)} client-months present in both match; totals tx {a.a.sum():,.0f} vs fees {ff.a.sum():,.0f}")
    # clients with no activity anywhere
    used = set()
    for ft in ["fact_fees", "fact_portfolio_snapshot", "fact_transactions"]:
        if ft in T:
            used |= set(T[ft].client_id)
    unused = ~c.client_id.isin(used)
    add_finding("WARN" if unused.any() else "INFO", G, "dim_client", "client_id", "client has no rows in any fact table",
                unused.sum(), len(c), "; ".join(c.loc[unused, "client_id"].head(5)))


# ----------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="folder with the 8 csv files (default hw04/data/raw)")
    ap.add_argument("--stage", default="raw")
    args = ap.parse_args()
    data_dir = Path(args.data) if args.data else HW_DIR / "data" / "raw"
    if not data_dir.is_absolute():
        data_dir = HW_DIR / data_dir
    out_dir = HW_DIR / "reports"
    out_dir.mkdir(exist_ok=True)

    print(f"Profiling {data_dir}")
    T = load_tables(data_dir)

    profile_rows = []
    for t, df in T.items():
        print(f"  {t:28} {len(df):>8,} rows x {df.shape[1]} cols")
        for col in df.columns:
            row, _ = profile_column(t, col, df[col])
            profile_rows.append(row)
        check_structural_blanks(t, df)
        check_duplicates(t, df)

    check_column_rules(T)
    check_client_near_duplicates(T)
    check_row_contradictions(T)
    check_referential_integrity(T)
    check_cross_table(T)

    prof = pd.DataFrame(profile_rows)
    summ = pd.DataFrame(findings)
    sev_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    summ = summ.sort_values(["severity", "check_group", "table"], key=lambda s: s.map(sev_order) if s.name == "severity" else s)
    prof.to_csv(out_dir / f"profile_{args.stage}.csv", index=False)
    summ.to_csv(out_dir / f"dq_summary_{args.stage}.csv", index=False)

    print("\nFindings by severity:", summ.severity.value_counts().to_dict())
    pd.set_option("display.width", 200, "display.max_colwidth", 70)
    print("\n--- ERROR and WARN findings ---")
    print(summ[summ.severity != "INFO"][["severity", "check_group", "table", "column", "check", "rows_affected"]]
          .to_string(index=False))
    print(f"\nSaved {out_dir / f'profile_{args.stage}.csv'} and {out_dir / f'dq_summary_{args.stage}.csv'}")


if __name__ == "__main__":
    main()